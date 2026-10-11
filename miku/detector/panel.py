#!/usr/bin/env python3
"""
面板检测和集成模块
"""
import os
import json
import sqlite3
from typing import List, Dict, Optional


class PanelDetector:
    """面板检测器"""

    def __init__(self):
        self.panels = []

    def detect_all(self) -> List[Dict]:
        """检测所有支持的面板"""
        self.panels = []

        # 检测 3x-ui
        if self._detect_3xui():
            pass

        # 检测 Xray原生
        if self._detect_xray():
            pass

        # 检测 Sing-box
        if self._detect_singbox():
            pass

        return self.panels

    def _detect_3xui(self) -> bool:
        """检测3x-ui面板"""
        if os.path.exists('/usr/local/x-ui/x-ui'):
            try:
                # 读取配置
                db_path = '/etc/x-ui/x-ui.db'
                web_port = 2053

                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT value FROM settings WHERE key='webPort'")
                    result = cursor.fetchone()
                    if result:
                        web_port = int(result[0])
                    conn.close()

                # 读取入站配置
                inbounds = self._read_3xui_inbounds()

                self.panels.append({
                    'name': '3x-ui',
                    'type': 'xray',
                    'version': self._get_3xui_version(),
                    'web_port': web_port,
                    'config_path': '/usr/local/x-ui/bin/config.json',
                    'inbounds': inbounds,
                    'status': 'detected'
                })
                return True

            except Exception as e:
                print(f"3x-ui检测异常: {e}")

        return False

    def _read_3xui_inbounds(self) -> List[Dict]:
        """读取3x-ui的入站配置"""
        inbounds = []
        try:
            db_path = '/etc/x-ui/x-ui.db'
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, user_id, up, down, total, remark, enable,
                           expiry_time, listen, port, protocol, settings,
                           stream_settings, tag, sniffing
                    FROM inbounds WHERE enable=1
                """)

                for row in cursor.fetchall():
                    try:
                        settings = json.loads(row[11]) if row[11] else {}
                        stream_settings = json.loads(row[12]) if row[12] else {}

                        inbound = {
                            'id': row[0],
                            'remark': row[5],
                            'port': row[9],
                            'protocol': row[10],
                            'network': stream_settings.get('network', 'tcp'),
                            'security': stream_settings.get('security', 'none'),
                            'enabled': bool(row[6])
                        }

                        # 提取TLS/Reality信息
                        if 'tlsSettings' in stream_settings:
                            inbound['tls_domain'] = stream_settings['tlsSettings'].get('serverName')
                        elif 'realitySettings' in stream_settings:
                            inbound['reality_dest'] = stream_settings['realitySettings'].get('dest')

                        inbounds.append(inbound)
                    except:
                        continue

                conn.close()

        except Exception as e:
            print(f"读取入站配置失败: {e}")

        return inbounds

    def _get_3xui_version(self) -> str:
        """获取3x-ui版本"""
        try:
            import subprocess
            result = subprocess.run(
                ['/usr/local/x-ui/x-ui', 'version'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return 'unknown'

    def _detect_xray(self) -> bool:
        """检测Xray原生安装"""
        if os.path.exists('/usr/local/bin/xray'):
            config_path = '/usr/local/etc/xray/config.json'
            inbounds = []

            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        inbounds = config.get('inbounds', [])
                except:
                    pass

            self.panels.append({
                'name': 'Xray (原生)',
                'type': 'xray',
                'config_path': config_path,
                'inbounds': inbounds,
                'status': 'detected'
            })
            return True

        return False

    def _detect_singbox(self) -> bool:
        """检测Sing-box"""
        if os.path.exists('/usr/local/bin/sing-box'):
            config_path = '/usr/local/etc/sing-box/config.json'
            inbounds = []

            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        inbounds = config.get('inbounds', [])
                except:
                    pass

            self.panels.append({
                'name': 'Sing-box',
                'type': 'singbox',
                'config_path': config_path,
                'inbounds': inbounds,
                'status': 'detected'
            })
            return True

        return False

    def get_panel_by_name(self, name: str) -> Optional[Dict]:
        """根据名称获取面板"""
        for panel in self.panels:
            if panel['name'] == name:
                return panel
        return None


if __name__ == '__main__':
    detector = PanelDetector()
    panels = detector.detect_all()

    print("=== 检测到的面板 ===\n")
    if panels:
        for i, panel in enumerate(panels, 1):
            print(f"{i}. {panel['name']}")
            if 'web_port' in panel:
                print(f"   Web端口: {panel['web_port']}")
            print(f"   入站数量: {len(panel.get('inbounds', []))}")
            if panel.get('inbounds'):
                for inbound in panel['inbounds'][:3]:  # 只显示前3个
                    print(f"     - {inbound.get('remark', 'N/A')} ({inbound.get('protocol')}) 端口 {inbound.get('port')}")
    else:
        print("未检测到已安装的面板")
