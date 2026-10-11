#!/usr/bin/env python3
"""
域名检测和SSL证书管理模块
"""
import os
import subprocess
import socket
import re
from typing import Optional, Dict, Tuple


class DomainManager:
    """域名和证书管理器"""

    def __init__(self, domain: Optional[str] = None):
        self.domain = domain
        self.cert_paths = {
            'cert': None,
            'key': None,
            'fullchain': None
        }

    def check_dns_resolution(self) -> Tuple[bool, Optional[str]]:
        """检查域名DNS解析"""
        if not self.domain:
            return False, "未设置域名"

        try:
            ip = socket.gethostbyname(self.domain)
            return True, ip
        except socket.gaierror:
            return False, "DNS解析失败"

    def detect_existing_certs(self) -> bool:
        """检测现有SSL证书"""
        # 检测 acme.sh 证书
        acme_path = os.path.expanduser(f'~/.acme.sh/{self.domain}')
        if os.path.exists(acme_path):
            cert_file = os.path.join(acme_path, f'{self.domain}.cer')
            key_file = os.path.join(acme_path, f'{self.domain}.key')
            fullchain_file = os.path.join(acme_path, 'fullchain.cer')

            if os.path.exists(cert_file) and os.path.exists(key_file):
                self.cert_paths = {
                    'cert': cert_file,
                    'key': key_file,
                    'fullchain': fullchain_file if os.path.exists(fullchain_file) else cert_file
                }
                return True

        # 检测 certbot 证书
        certbot_path = f'/etc/letsencrypt/live/{self.domain}'
        if os.path.exists(certbot_path):
            self.cert_paths = {
                'cert': f'{certbot_path}/cert.pem',
                'key': f'{certbot_path}/privkey.pem',
                'fullchain': f'{certbot_path}/fullchain.pem'
            }
            return True

        # 检测 3x-ui 证书目录
        xui_cert_path = f'/root/cert/{self.domain}'
        if os.path.exists(xui_cert_path):
            cert_file = f'{xui_cert_path}/cert.crt'
            key_file = f'{xui_cert_path}/private.key'
            if os.path.exists(cert_file) and os.path.exists(key_file):
                self.cert_paths = {
                    'cert': cert_file,
                    'key': key_file,
                    'fullchain': cert_file
                }
                return True

        return False

    def request_cert_acme(self, email: str) -> bool:
        """使用acme.sh申请证书"""
        try:
            # 安装 acme.sh
            if not os.path.exists(os.path.expanduser('~/.acme.sh')):
                print("正在安装 acme.sh...")
                subprocess.run(
                    ['curl', 'https://get.acme.sh', '|', 'sh'],
                    shell=True,
                    check=True
                )

            # 申请证书
            print(f"正在为 {self.domain} 申请证书...")
            subprocess.run([
                os.path.expanduser('~/.acme.sh/acme.sh'),
                '--issue',
                '-d', self.domain,
                '--standalone',
                '--httpport', '80',
                '--email', email
            ], check=True)

            # 安装证书
            cert_dir = os.path.expanduser(f'~/.acme.sh/{self.domain}')
            if os.path.exists(cert_dir):
                self.cert_paths = {
                    'cert': f'{cert_dir}/{self.domain}.cer',
                    'key': f'{cert_dir}/{self.domain}.key',
                    'fullchain': f'{cert_dir}/fullchain.cer'
                }
                return True

        except Exception as e:
            print(f"证书申请失败: {e}")
            return False

        return False

    def get_cert_info(self) -> Optional[Dict]:
        """获取证书信息"""
        if not self.cert_paths['cert']:
            return None

        try:
            result = subprocess.run(
                ['openssl', 'x509', '-in', self.cert_paths['cert'],
                 '-noout', '-dates', '-subject'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                info = {}
                for line in lines:
                    if 'notBefore' in line:
                        info['valid_from'] = line.split('=')[1]
                    elif 'notAfter' in line:
                        info['valid_until'] = line.split('=')[1]
                    elif 'subject' in line:
                        info['subject'] = line.split('=', 1)[1]
                return info

        except Exception as e:
            print(f"获取证书信息失败: {e}")

        return None


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法: python domain.py <域名>")
        sys.exit(1)

    domain = sys.argv[1]
    manager = DomainManager(domain)

    print(f"=== 检查域名: {domain} ===\n")

    # DNS解析
    success, result = manager.check_dns_resolution()
    if success:
        print(f"✓ DNS解析成功: {result}")
    else:
        print(f"✗ DNS解析失败: {result}")

    # 证书检测
    if manager.detect_existing_certs():
        print(f"✓ 找到现有证书")
        print(f"  证书文件: {manager.cert_paths['cert']}")
        print(f"  私钥文件: {manager.cert_paths['key']}")

        cert_info = manager.get_cert_info()
        if cert_info:
            print(f"  有效期至: {cert_info['valid_until']}")
    else:
        print("✗ 未找到现有证书")
