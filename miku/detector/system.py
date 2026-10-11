#!/usr/bin/env python3
"""
系统环境检测模块
检测操作系统、依赖工具、已安装的面板等
"""
import os
import subprocess
import platform
from typing import Dict, List, Optional


class SystemDetector:
    """系统环境检测器"""

    def __init__(self):
        self.os_type = platform.system()
        self.os_release = self._get_os_release()
        self.missing_tools = []
        self.installed_panels = []

    def _get_os_release(self) -> Dict[str, str]:
        """获取操作系统发行版信息"""
        info = {}
        try:
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        info[key] = value.strip('"')
        except FileNotFoundError:
            pass
        return info

    def check_required_tools(self) -> List[str]:
        """检测必需的工具是否已安装"""
        required_tools = [
            'curl',
            'wget',
            'openvpn',
            'socat',
            'iptables',
            'ip',  # iproute2
            'systemctl',
            'openssl'
        ]

        missing = []
        for tool in required_tools:
            if not self._command_exists(tool):
                missing.append(tool)

        self.missing_tools = missing
        return missing

    def _command_exists(self, cmd: str) -> bool:
        """检查命令是否存在"""
        try:
            subprocess.run(
                ['which', cmd],
                capture_output=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def detect_panels(self) -> List[Dict]:
        """检测已安装的节点面板"""
        panels = []

        # 检测 3x-ui
        if os.path.exists('/usr/local/x-ui/x-ui'):
            panels.append({
                'name': '3x-ui',
                'type': 'xray',
                'path': '/usr/local/x-ui',
                'config_path': '/usr/local/x-ui/bin/config.json',
                'status': self._check_service_status('x-ui'),
                'port': self._detect_3xui_web_port()
            })

        # 检测 X-UI (旧版)
        if os.path.exists('/usr/local/x-ui') and not os.path.exists('/usr/local/x-ui/x-ui'):
            panels.append({
                'name': 'X-UI',
                'type': 'xray',
                'path': '/usr/local/x-ui',
                'status': self._check_service_status('x-ui')
            })

        # 检测 V2board
        if os.path.exists('/www/wwwroot/v2board'):
            panels.append({
                'name': 'V2board',
                'type': 'v2ray',
                'path': '/www/wwwroot/v2board',
                'status': 'unknown'
            })

        # 检测原生 Xray
        if os.path.exists('/usr/local/bin/xray'):
            panels.append({
                'name': 'Xray (原生)',
                'type': 'xray',
                'path': '/usr/local/etc/xray',
                'config_path': '/usr/local/etc/xray/config.json',
                'status': self._check_service_status('xray')
            })

        # 检测 Sing-box
        if os.path.exists('/usr/local/bin/sing-box'):
            panels.append({
                'name': 'Sing-box',
                'type': 'singbox',
                'path': '/usr/local/etc/sing-box',
                'config_path': '/usr/local/etc/sing-box/config.json',
                'status': self._check_service_status('sing-box')
            })

        self.installed_panels = panels
        return panels

    def _check_service_status(self, service_name: str) -> str:
        """检查 systemd 服务状态"""
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True
            )
            status = result.stdout.strip()
            return status if status in ['active', 'inactive', 'failed'] else 'unknown'
        except:
            return 'unknown'

    def _detect_3xui_web_port(self) -> Optional[int]:
        """检测 3x-ui Web 端口"""
        try:
            # 读取 3x-ui 数据库
            import sqlite3
            db_path = '/etc/x-ui/x-ui.db'
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key='webPort'")
                result = cursor.fetchone()
                conn.close()
                if result:
                    return int(result[0])
        except:
            pass
        return None

    def get_system_info(self) -> Dict:
        """获取完整的系统信息"""
        return {
            'os_type': self.os_type,
            'os_name': self.os_release.get('NAME', 'Unknown'),
            'os_version': self.os_release.get('VERSION', 'Unknown'),
            'kernel': platform.release(),
            'architecture': platform.machine(),
            'python_version': platform.python_version()
        }

    def check_network(self) -> bool:
        """检查网络连接"""
        try:
            subprocess.run(
                ['ping', '-c', '1', '-W', '3', '8.8.8.8'],
                capture_output=True,
                check=True
            )
            return True
        except:
            return False

    def check_root(self) -> bool:
        """检查是否为 root 权限"""
        return os.geteuid() == 0

    def get_public_ip(self) -> Optional[str]:
        """获取公网 IP"""
        try:
            result = subprocess.run(
                ['curl', '-s', '--max-time', '5', 'https://api.ipify.org'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None


if __name__ == '__main__':
    detector = SystemDetector()

    print("=== 系统信息 ===")
    info = detector.get_system_info()
    for key, value in info.items():
        print(f"{key}: {value}")

    print("\n=== 检查权限 ===")
    if detector.check_root():
        print("✓ Root 权限")
    else:
        print("✗ 需要 Root 权限")

    print("\n=== 检查网络 ===")
    if detector.check_network():
        ip = detector.get_public_ip()
        print(f"✓ 网络正常 (公网IP: {ip})")
    else:
        print("✗ 网络异常")

    print("\n=== 检查依赖工具 ===")
    missing = detector.check_required_tools()
    if missing:
        print(f"✗ 缺少工具: {', '.join(missing)}")
    else:
        print("✓ 所有工具已安装")

    print("\n=== 检测已安装面板 ===")
    panels = detector.detect_panels()
    if panels:
        for panel in panels:
            print(f"✓ {panel['name']} - {panel['status']}")
            if 'port' in panel and panel['port']:
                print(f"  Web端口: {panel['port']}")
    else:
        print("未检测到已安装的面板")
