#!/usr/bin/env python3
"""
OpenVPN 隧道管理
使用 Network Namespace 隔离
"""
import os
import subprocess
import time
import tempfile
from typing import Optional


class OpenVPNTunnel:
    """OpenVPN 隧道管理器"""

    def __init__(self, tunnel_id: str, country_code: str):
        self.tunnel_id = tunnel_id
        self.country_code = country_code
        self.netns_name = f"miku_{country_code.lower()}"
        self.config_file = None
        self.process = None
        self.socks_port = None

    def create_netns(self) -> bool:
        """创建网络命名空间"""
        try:
            # 创建 netns
            subprocess.run(
                ['ip', 'netns', 'add', self.netns_name],
                check=True,
                capture_output=True
            )

            # 启动 loopback
            subprocess.run(
                ['ip', 'netns', 'exec', self.netns_name,
                 'ip', 'link', 'set', 'lo', 'up'],
                check=True,
                capture_output=True
            )

            print(f"✅ 创建网络命名空间: {self.netns_name}")
            return True

        except subprocess.CalledProcessError as e:
            # 如果已存在则跳过
            if 'File exists' not in str(e.stderr):
                print(f"❌ 创建 netns 失败: {e}")
                return False
            return True

    def start_openvpn(self, ovpn_config: str) -> bool:
        """在 netns 中启动 OpenVPN"""
        try:
            # 写入配置文件
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.ovpn',
                delete=False
            ) as f:
                f.write(ovpn_config)
                self.config_file = f.name

            os.chmod(self.config_file, 0o600)

            # 在 netns 中启动 OpenVPN
            log_file = f'/var/log/miku/tunnel_{self.country_code}.log'

            cmd = [
                'ip', 'netns', 'exec', self.netns_name,
                'openvpn',
                '--config', self.config_file,
                '--daemon',
                '--log', log_file
            ]

            subprocess.run(cmd, check=True)

            print(f"✅ OpenVPN 已启动: {self.netns_name}")

            # 等待连接建立
            if self.wait_for_connection():
                return True
            else:
                print("❌ 连接超时")
                return False

        except Exception as e:
            print(f"❌ 启动 OpenVPN 失败: {e}")
            return False

    def wait_for_connection(self, timeout: int = 30) -> bool:
        """等待 VPN 连接建立"""
        print(f"等待 VPN 连接建立...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # 检查 tun 设备
                result = subprocess.run(
                    ['ip', 'netns', 'exec', self.netns_name,
                     'ip', 'link', 'show', 'tun0'],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    print("✅ VPN 连接已建立")
                    return True

            except:
                pass

            time.sleep(2)

        return False

    def get_exit_ip(self) -> Optional[str]:
        """获取出口 IP"""
        try:
            result = subprocess.run(
                ['ip', 'netns', 'exec', self.netns_name,
                 'curl', '-s', '--max-time', '10',
                 'https://api.ipify.org'],
                capture_output=True,
                text=True,
                timeout=12
            )

            if result.returncode == 0:
                return result.stdout.strip()

        except Exception as e:
            print(f"获取出口 IP 失败: {e}")

        return None

    def start_socks_proxy(self, port: int) -> bool:
        """在 netns 中启动 SOCKS5 代理"""
        self.socks_port = port

        try:
            # 使用 socat 创建 SOCKS 代理
            # 这是简化版本，生产环境需要更复杂的实现
            cmd = [
                'ip', 'netns', 'exec', self.netns_name,
                'socat',
                f'TCP-LISTEN:{port},reuseaddr,fork',
                'SOCKS4A:localhost:0,socksport=1080'
            ]

            # 后台运行
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            print(f"✅ SOCKS5 代理已启动: 端口 {port}")
            return True

        except Exception as e:
            print(f"❌ 启动 SOCKS5 代理失败: {e}")
            return False

    def stop(self):
        """停止隧道"""
        try:
            # 停止 OpenVPN
            subprocess.run(
                ['ip', 'netns', 'exec', self.netns_name,
                 'killall', 'openvpn'],
                capture_output=True
            )

            # 停止代理进程
            if self.process:
                self.process.terminate()
                self.process.wait(timeout=5)

            # 删除 netns
            subprocess.run(
                ['ip', 'netns', 'del', self.netns_name],
                capture_output=True
            )

            # 删除配置文件
            if self.config_file and os.path.exists(self.config_file):
                os.unlink(self.config_file)

            print(f"✅ 隧道已停止: {self.netns_name}")

        except Exception as e:
            print(f"停止隧道时出错: {e}")

    def is_alive(self) -> bool:
        """检查隧道是否存活"""
        try:
            # 检查 netns 是否存在
            result = subprocess.run(
                ['ip', 'netns', 'list'],
                capture_output=True,
                text=True
            )

            if self.netns_name not in result.stdout:
                return False

            # 检查能否获取出口 IP
            exit_ip = self.get_exit_ip()
            return exit_ip is not None

        except:
            return False


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法: python tunnel.py <配置文件>")
        sys.exit(1)

    config_file = sys.argv[1]

    with open(config_file, 'r') as f:
        ovpn_config = f.read()

    tunnel = OpenVPNTunnel('test1', 'JP')

    print("创建隧道...")
    if tunnel.create_netns():
        if tunnel.start_openvpn(ovpn_config):
            exit_ip = tunnel.get_exit_ip()
            print(f"出口 IP: {exit_ip}")

            print("\n按 Ctrl+C 停止...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n停止隧道...")
                tunnel.stop()
