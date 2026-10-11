#!/usr/bin/env python3
"""
主交互式安装向导
"""
import sys
import os
from typing import Optional, Dict, List

from miku.detector.system import SystemDetector
from miku.detector.domain import DomainManager
from miku.detector.panel import PanelDetector


class InstallWizard:
    """交互式安装向导"""

    def __init__(self):
        self.system = SystemDetector()
        self.domain_manager: Optional[DomainManager] = None
        self.panel_detector = PanelDetector()

        self.config = {
            'domain': None,
            'use_domain': False,
            'panel': None,
            'use_existing_panel': False,
            'selected_inbound': None,
            'inbound_type': None,
            'countries': [],
            'selected_nodes': []
        }

    def run(self):
        """运行安装向导"""
        self.print_banner()

        # 1. 检查环境
        if not self.check_environment():
            return False

        # 2. 询问域名
        self.ask_domain()

        # 3. 检测面板
        self.detect_panels()

        # 4. 配置入口节点
        self.configure_inbound()

        # 5. 选择出口节点
        self.select_outbound()

        # 6. 确认并安装
        self.confirm_and_install()

        return True

    def print_banner(self):
        """打印欢迎横幅"""
        print("""
╔════════════════════════════════════════════════════════╗
║                                                        ║
║        🎵 Miku-GateVPN 智能节点制作工具 v2.0          ║
║                                                        ║
║        为您快速创建高质量翻墙节点                      ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
        """)

    def check_environment(self) -> bool:
        """检查系统环境"""
        print("\n📋 正在检查系统环境...\n")

        # 检查 root
        if not self.system.check_root():
            print("❌ 需要 root 权限运行此脚本")
            print("   请使用: sudo python3 install_wizard.py")
            return False
        print("✅ Root 权限")

        # 检查网络
        if not self.system.check_network():
            print("❌ 网络连接失败")
            return False

        ip = self.system.get_public_ip()
        print(f"✅ 网络正常 (公网IP: {ip})")

        # 检查系统信息
        info = self.system.get_system_info()
        print(f"✅ {info['os_name']} {info['os_version']}")

        # 检查依赖
        missing = self.system.check_required_tools()
        if missing:
            print(f"\n⚠️  缺少以下工具: {', '.join(missing)}")
            answer = input("是否现在安装? [Y/n]: ").strip().lower()
            if answer != 'n':
                print("正在安装依赖...")
                # TODO: 调用安装函数
                print("✅ 依赖安装完成")
            else:
                print("❌ 缺少必需工具，无法继续")
                return False
        else:
            print("✅ 所有依赖已安装")

        return True

    def ask_domain(self):
        """询问域名配置"""
        print("\n🌐 域名配置")
        print("-" * 60)

        answer = input("是否绑定域名? [y/N]: ").strip().lower()

        if answer == 'y':
            domain = input("请输入域名 (例如: miku.example.com): ").strip()

            if domain:
                self.domain_manager = DomainManager(domain)
                self.config['domain'] = domain
                self.config['use_domain'] = True

                # 检查 DNS
                print(f"\n正在检查 {domain} 的 DNS 解析...")
                success, result = self.domain_manager.check_dns_resolution()

                if success:
                    print(f"✅ DNS 解析成功: {result}")

                    # 检查证书
                    if self.domain_manager.detect_existing_certs():
                        print("✅ 找到现有 SSL 证书")
                        cert_info = self.domain_manager.get_cert_info()
                        if cert_info:
                            print(f"   有效期至: {cert_info['valid_until']}")
                    else:
                        print("⚠️  未找到 SSL 证书")
                        answer = input("是否现在申请 Let's Encrypt 证书? [Y/n]: ").strip().lower()
                        if answer != 'n':
                            email = input("请输入邮箱地址: ").strip()
                            print("正在申请证书...")
                            if self.domain_manager.request_cert_acme(email):
                                print("✅ 证书申请成功")
                            else:
                                print("❌ 证书申请失败，将使用自签证书")
                else:
                    print(f"❌ DNS 解析失败: {result}")
                    print("   请先配置域名 A 记录指向本服务器 IP")
                    self.config['use_domain'] = False
        else:
            print("将使用服务器 IP 地址访问")
            self.config['use_domain'] = False

    def detect_panels(self):
        """检测已安装的面板"""
        print("\n🔍 正在检测已安装的面板...\n")

        panels = self.panel_detector.detect_all()

        if panels:
            print("检测到以下面板:\n")
            for i, panel in enumerate(panels, 1):
                print(f"  {i}. {panel['name']}")
                if 'web_port' in panel:
                    print(f"     Web 端口: {panel['web_port']}")
                if panel.get('inbounds'):
                    print(f"     入站节点: {len(panel['inbounds'])} 个")

            print()
            answer = input("是否使用现有面板? [Y/n]: ").strip().lower()

            if answer != 'n':
                choice = input(f"请选择面板 [1-{len(panels)}]: ").strip()
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(panels):
                        self.config['panel'] = panels[idx]
                        self.config['use_existing_panel'] = True
                        print(f"✅ 已选择: {panels[idx]['name']}")
                except:
                    print("⚠️  无效选择，将创建新配置")
        else:
            print("未检测到已安装的面板")
            print("将创建新的 Xray 配置")

    def configure_inbound(self):
        """配置入口节点"""
        print("\n📥 配置入口节点")
        print("-" * 60)

        if self.config['use_existing_panel'] and self.config['panel']:
            # 使用现有入站
            inbounds = self.config['panel'].get('inbounds', [])

            if inbounds:
                print("\n检测到现有入站节点:\n")
                for i, inbound in enumerate(inbounds, 1):
                    print(f"  {i}. {inbound.get('remark', 'N/A')}")
                    print(f"     协议: {inbound.get('protocol')}")
                    print(f"     端口: {inbound.get('port')}")
                    print(f"     网络: {inbound.get('network')}")
                    print()

                answer = input("是否使用这些节点作为入口? [Y/n]: ").strip().lower()

                if answer != 'n':
                    choice = input(f"请选择入站 [1-{len(inbounds)}]: ").strip()
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(inbounds):
                            self.config['selected_inbound'] = inbounds[idx]
                            print(f"✅ 已选择: {inbounds[idx].get('remark')}")
                            return
                    except:
                        pass

        # 创建新入站
        print("\n请选择入口节点类型:\n")
        print("  1. VLESS + TCP + TLS + Vision (推荐)")
        print("  2. VLESS + TCP + Reality")
        print("  3. VMess + WebSocket + TLS")
        print("  4. Trojan + TCP + TLS")
        print("  5. Hysteria2")
        print()

        choice = input("请选择 [1-5]: ").strip()

        inbound_types = {
            '1': 'vless-tcp-tls-vision',
            '2': 'vless-tcp-reality',
            '3': 'vmess-ws-tls',
            '4': 'trojan-tcp-tls',
            '5': 'hysteria2'
        }

        self.config['inbound_type'] = inbound_types.get(choice, 'vless-tcp-tls-vision')
        print(f"✅ 已选择: {self.config['inbound_type']}")

        # TODO: 配置具体参数

    def select_outbound(self):
        """选择出口节点"""
        print("\n📤 选择出口节点")
        print("-" * 60)

        print("\n正在从 VPN Gate 获取节点列表...")
        # TODO: 获取节点列表

        print("\n请选择出口国家:\n")
        print("  1. 日本 (JP)")
        print("  2. 美国 (US)")
        print("  3. 韩国 (KR)")
        print("  4. 台湾 (TW)")
        print("  5. 英国 (UK)")
        print()

        choices = input("请选择国家 (多选用逗号分隔，例如: 1,2,3): ").strip()

        country_map = {
            '1': 'JP',
            '2': 'US',
            '3': 'KR',
            '4': 'TW',
            '5': 'UK'
        }

        selected = []
        for c in choices.split(','):
            c = c.strip()
            if c in country_map:
                selected.append(country_map[c])

        self.config['countries'] = selected
        print(f"✅ 已选择: {', '.join(selected)}")

    def confirm_and_install(self):
        """确认配置并安装"""
        print("\n" + "="*60)
        print("配置确认")
        print("="*60)

        print(f"\n域名: {self.config['domain'] if self.config['use_domain'] else '使用 IP'}")
        print(f"面板: {self.config['panel']['name'] if self.config['use_existing_panel'] else '新建'}")
        print(f"入口: {self.config['inbound_type'] or '现有节点'}")
        print(f"出口: {', '.join(self.config['countries'])}")

        print()
        answer = input("确认以上配置并开始安装? [Y/n]: ").strip().lower()

        if answer == 'n':
            print("已取消安装")
            return

        print("\n正在安装...")
        print("⏳ 这可能需要几分钟时间...\n")

        # TODO: 执行实际安装

        print("✅ 安装完成!")
        print("\n" + "="*60)
        self.print_access_info()

    def print_access_info(self):
        """打印访问信息"""
        print("访问信息")
        print("="*60)

        if self.config['use_domain']:
            web_url = f"https://{self.config['domain']}:8787"
        else:
            ip = self.system.get_public_ip()
            web_url = f"http://{ip}:8787"

        print(f"\nWeb 管理界面: {web_url}")
        print(f"订阅链接: {web_url}/sub/xxxxx")

        print("\n管理命令:")
        print("  miku status    - 查看节点状态")
        print("  miku switch    - 切换出口节点")
        print("  miku logs      - 查看日志")

        print()


def main():
    """主函数"""
    wizard = InstallWizard()
    try:
        wizard.run()
    except KeyboardInterrupt:
        print("\n\n已取消安装")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 安装失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
