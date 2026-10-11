#!/usr/bin/env python3
"""
Web 管理面板 - Flask 应用
所有配置和管理通过 Web 界面完成
"""
from flask import Flask, render_template, jsonify, request, session, redirect, url_for
from flask_socketio import SocketIO, emit
import secrets
import os
import json
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
socketio = SocketIO(app, cors_allowed_origins="*")

# 全局状态
manager_state = {
    'system_info': None,
    'panels': [],
    'domain': None,
    'inbound_config': None,
    'tunnels': {},
    'setup_complete': False
}


def require_setup(f):
    """需要完成初始设置"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not manager_state['setup_complete'] and request.endpoint != 'setup':
            return redirect(url_for('setup'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """首页 - 重定向到设置或仪表盘"""
    if not manager_state['setup_complete']:
        return redirect(url_for('setup'))
    return redirect(url_for('dashboard'))


@app.route('/setup')
def setup():
    """初始设置向导页面"""
    return render_template('setup.html')


@app.route('/dashboard')
@require_setup
def dashboard():
    """主仪表盘"""
    return render_template('dashboard.html')


@app.route('/tunnels')
@require_setup
def tunnels():
    """隧道管理页面"""
    return render_template('tunnels.html')


@app.route('/nodes')
@require_setup
def nodes():
    """节点管理页面"""
    return render_template('nodes.html')


@app.route('/settings')
@require_setup
def settings():
    """设置页面"""
    return render_template('settings.html')


# ============ API 端点 ============

@app.route('/api/system/detect', methods=['POST'])
def api_system_detect():
    """检测系统环境"""
    try:
        from miku.detector.system import SystemDetector

        detector = SystemDetector()

        result = {
            'info': detector.get_system_info(),
            'is_root': detector.check_root(),
            'has_network': detector.check_network(),
            'public_ip': detector.get_public_ip(),
            'missing_tools': detector.check_required_tools(),
            'panels': detector.detect_panels()
        }

        manager_state['system_info'] = result
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/panels/detect', methods=['POST'])
def api_panels_detect():
    """检测已安装面板"""
    try:
        from miku.detector.panel import PanelDetector

        detector = PanelDetector()
        panels = detector.detect_all()

        manager_state['panels'] = panels
        return jsonify({'success': True, 'data': panels})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/domain/check', methods=['POST'])
def api_domain_check():
    """检查域名"""
    try:
        from miku.detector.domain import DomainManager

        data = request.json
        domain = data.get('domain')

        manager = DomainManager(domain)
        success, result = manager.check_dns_resolution()

        response = {
            'dns_resolved': success,
            'dns_ip': result,
            'has_cert': manager.detect_existing_certs(),
            'cert_paths': manager.cert_paths if success else None
        }

        if success:
            manager_state['domain'] = {
                'name': domain,
                'manager': manager,
                **response
            }

        return jsonify({'success': True, 'data': response})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/domain/request-cert', methods=['POST'])
def api_domain_request_cert():
    """申请 SSL 证书"""
    try:
        data = request.json
        email = data.get('email')

        if not manager_state.get('domain'):
            return jsonify({'success': False, 'error': '请先设置域名'}), 400

        domain_manager = manager_state['domain']['manager']
        success = domain_manager.request_cert_acme(email)

        return jsonify({'success': success})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vpngate/countries', methods=['GET'])
def api_vpngate_countries():
    """获取 VPN Gate 可用国家"""
    try:
        from miku.outbound.vpngate import VPNGateClient

        client = VPNGateClient()
        client.fetch_nodes()
        countries = client.get_available_countries()

        return jsonify({
            'success': True,
            'data': [
                {'code': code, 'name': name, 'count': count}
                for code, name, count in countries
            ]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/vpngate/nodes/<country_code>', methods=['GET'])
def api_vpngate_nodes(country_code):
    """获取指定国家的节点列表"""
    try:
        from miku.outbound.vpngate import VPNGateClient

        limit = request.args.get('limit', 20, type=int)

        client = VPNGateClient()
        client.fetch_nodes()
        nodes = client.get_best_nodes(country_code, limit)

        return jsonify({
            'success': True,
            'data': [{
                'ip': node['ip'],
                'hostname': node['hostname'],
                'country': node['country'],
                'country_code': node['country_code'],
                'ping': node['ping'],
                'speed_mbps': node['speed'] // 1_000_000,
                'sessions': node['sessions'],
                'quality_score': node['quality_score'],
                'is_residential': client.is_residential(node)
            } for node in nodes]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/nodes/check', methods=['POST'])
def api_nodes_check():
    """检测节点质量"""
    try:
        from miku.outbound.checker import NodeQualityChecker

        data = request.json
        ips = data.get('ips', [])

        checker = NodeQualityChecker()
        results = checker.batch_check(ips, max_workers=10)

        return jsonify({'success': True, 'data': results})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/inbound/generate', methods=['POST'])
def api_inbound_generate():
    """生成入口配置"""
    try:
        from miku.inbound.xray import XrayConfigGenerator

        data = request.json
        protocol = data.get('protocol')
        port = data.get('port', 443)

        generator = XrayConfigGenerator()

        if protocol == 'vless-reality':
            target = data.get('reality_target')
            config = generator.generate_vless_reality(port, target)
        elif protocol == 'vless-tls-vision':
            cert = data.get('cert_file')
            key = data.get('key_file')
            config = generator.generate_vless_tls_vision(port, cert, key)
        elif protocol == 'vmess-ws-tls':
            path = data.get('ws_path', '/vmess')
            cert = data.get('cert_file')
            key = data.get('key_file')
            config = generator.generate_vmess_ws_tls(port, path, cert, key)
        elif protocol == 'trojan-tls':
            cert = data.get('cert_file')
            key = data.get('key_file')
            config = generator.generate_trojan_tls(port, None, cert, key)
        else:
            return jsonify({'success': False, 'error': '不支持的协议'}), 400

        manager_state['inbound_config'] = config
        return jsonify({'success': True, 'data': config})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tunnels/create', methods=['POST'])
def api_tunnels_create():
    """创建隧道"""
    try:
        from miku.outbound.tunnel import OpenVPNTunnel
        from miku.outbound.vpngate import VPNGateClient

        data = request.json
        country_code = data.get('country_code')
        node_ip = data.get('node_ip')

        # 获取节点配置
        client = VPNGateClient()
        client.fetch_nodes()

        node = None
        for n in client.nodes:
            if n['ip'] == node_ip:
                node = n
                break

        if not node:
            return jsonify({'success': False, 'error': '节点不存在'}), 404

        # 创建隧道
        tunnel_id = f"tunnel_{country_code}_{len(manager_state['tunnels'])}"
        tunnel = OpenVPNTunnel(tunnel_id, country_code)

        # 在后台启动（异步）
        if tunnel.create_netns():
            if tunnel.start_openvpn(node['ovpn_config']):
                manager_state['tunnels'][tunnel_id] = {
                    'id': tunnel_id,
                    'country_code': country_code,
                    'node_ip': node_ip,
                    'status': 'connected',
                    'tunnel': tunnel
                }

                return jsonify({
                    'success': True,
                    'data': {
                        'tunnel_id': tunnel_id,
                        'exit_ip': tunnel.get_exit_ip()
                    }
                })

        return jsonify({'success': False, 'error': '隧道启动失败'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/tunnels/list', methods=['GET'])
def api_tunnels_list():
    """获取隧道列表"""
    tunnels = []

    for tunnel_id, info in manager_state['tunnels'].items():
        tunnel = info['tunnel']
        tunnels.append({
            'id': tunnel_id,
            'country_code': info['country_code'],
            'node_ip': info['node_ip'],
            'status': 'connected' if tunnel.is_alive() else 'disconnected',
            'exit_ip': tunnel.get_exit_ip(),
            'socks_port': tunnel.socks_port
        })

    return jsonify({'success': True, 'data': tunnels})


@app.route('/api/tunnels/<tunnel_id>/stop', methods=['POST'])
def api_tunnels_stop(tunnel_id):
    """停止隧道"""
    try:
        if tunnel_id not in manager_state['tunnels']:
            return jsonify({'success': False, 'error': '隧道不存在'}), 404

        tunnel = manager_state['tunnels'][tunnel_id]['tunnel']
        tunnel.stop()

        del manager_state['tunnels'][tunnel_id]

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/setup/complete', methods=['POST'])
def api_setup_complete():
    """完成初始设置"""
    try:
        data = request.json

        # 保存配置
        config = {
            'domain': data.get('domain'),
            'inbound_type': data.get('inbound_type'),
            'selected_countries': data.get('countries', [])
        }

        # 写入配置文件
        with open('/etc/miku/config.json', 'w') as f:
            json.dump(config, f, indent=2)

        manager_state['setup_complete'] = True

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============ WebSocket 事件 ============

@socketio.on('connect')
def handle_connect():
    """客户端连接"""
    emit('status', {'connected': True})


@socketio.on('disconnect')
def handle_disconnect():
    """客户端断开"""
    pass


@socketio.on('check_tunnel_status')
def handle_check_tunnel_status():
    """实时检查隧道状态"""
    tunnels = []

    for tunnel_id, info in manager_state['tunnels'].items():
        tunnel = info['tunnel']
        tunnels.append({
            'id': tunnel_id,
            'status': 'connected' if tunnel.is_alive() else 'disconnected',
            'exit_ip': tunnel.get_exit_ip()
        })

    emit('tunnel_status', tunnels)


if __name__ == '__main__':
    # 创建必要目录
    os.makedirs('/etc/miku', exist_ok=True)

    # 启动服务器
    port = int(os.environ.get('MIKU_WEB_PORT', 8787))

    print(f"""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║        🎵 Miku-GateVPN Web 管理面板                        ║
║                                                            ║
║        访问地址: http://0.0.0.0:{port}                    ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)

    socketio.run(app, host='0.0.0.0', port=port, debug=False)
