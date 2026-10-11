#!/usr/bin/env python3
"""
Xray 配置生成器
支持多种协议配置
"""
import json
import uuid
import secrets
import subprocess
from typing import Dict, Optional


class XrayConfigGenerator:
    """Xray 配置生成器"""

    # Reality 推荐目标域名
    REALITY_TARGETS = [
        'www.microsoft.com:443',
        'www.apple.com:443',
        'www.cloudflare.com:443',
        'www.amazon.com:443',
        'www.google.com:443',
        'www.samsung.com:443',
        'www.cisco.com:443',
        'www.oracle.com:443',
        'www.ibm.com:443',
        'www.adobe.com:443'
    ]

    def __init__(self):
        pass

    @staticmethod
    def generate_uuid() -> str:
        """生成随机 UUID"""
        return str(uuid.uuid4())

    @staticmethod
    def generate_reality_keypair() -> tuple:
        """生成 Reality 密钥对"""
        try:
            result = subprocess.run(
                ['xray', 'x25519'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                private_key = lines[0].split(':')[1].strip()
                public_key = lines[1].split(':')[1].strip()
                return private_key, public_key

        except Exception as e:
            print(f"生成密钥对失败: {e}")

        return None, None

    @staticmethod
    def generate_short_id() -> str:
        """生成 Reality Short ID"""
        return secrets.token_hex(8)

    def generate_vless_reality(
        self,
        port: int = 443,
        target_domain: Optional[str] = None,
        server_names: Optional[list] = None
    ) -> Dict:
        """
        生成 VLESS + Reality 配置
        """
        if not target_domain:
            target_domain = self.REALITY_TARGETS[0]

        if not server_names:
            server_names = [target_domain.split(':')[0]]

        private_key, public_key = self.generate_reality_keypair()

        config = {
            "tag": "vless-reality-in",
            "port": port,
            "protocol": "vless",
            "settings": {
                "clients": [{
                    "id": self.generate_uuid(),
                    "flow": "xtls-rprx-vision"
                }],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "tcp",
                "security": "reality",
                "realitySettings": {
                    "show": False,
                    "dest": target_domain,
                    "xver": 0,
                    "serverNames": server_names,
                    "privateKey": private_key,
                    "shortIds": [
                        self.generate_short_id(),
                        ""
                    ]
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }

        # 返回配置和公钥（用于客户端）
        return {
            "inbound": config,
            "public_key": public_key,
            "client_id": config["settings"]["clients"][0]["id"]
        }

    def generate_vless_tls_vision(
        self,
        port: int = 443,
        cert_file: str = "/path/to/cert.pem",
        key_file: str = "/path/to/key.pem"
    ) -> Dict:
        """
        生成 VLESS + TLS + Vision 配置
        """
        config = {
            "tag": "vless-tls-in",
            "port": port,
            "protocol": "vless",
            "settings": {
                "clients": [{
                    "id": self.generate_uuid(),
                    "flow": "xtls-rprx-vision"
                }],
                "decryption": "none"
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {
                    "certificates": [{
                        "certificateFile": cert_file,
                        "keyFile": key_file
                    }],
                    "alpn": ["h2", "http/1.1"]
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }

        return {
            "inbound": config,
            "client_id": config["settings"]["clients"][0]["id"]
        }

    def generate_vmess_ws_tls(
        self,
        port: int = 443,
        path: str = "/vmess",
        cert_file: str = "/path/to/cert.pem",
        key_file: str = "/path/to/key.pem"
    ) -> Dict:
        """
        生成 VMess + WebSocket + TLS 配置
        """
        config = {
            "tag": "vmess-ws-in",
            "port": port,
            "protocol": "vmess",
            "settings": {
                "clients": [{
                    "id": self.generate_uuid(),
                    "alterId": 0
                }]
            },
            "streamSettings": {
                "network": "ws",
                "security": "tls",
                "wsSettings": {
                    "path": path
                },
                "tlsSettings": {
                    "certificates": [{
                        "certificateFile": cert_file,
                        "keyFile": key_file
                    }],
                    "alpn": ["h2", "http/1.1"]
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }

        return {
            "inbound": config,
            "client_id": config["settings"]["clients"][0]["id"]
        }

    def generate_trojan_tls(
        self,
        port: int = 443,
        password: Optional[str] = None,
        cert_file: str = "/path/to/cert.pem",
        key_file: str = "/path/to/key.pem"
    ) -> Dict:
        """
        生成 Trojan + TLS 配置
        """
        if not password:
            password = secrets.token_urlsafe(16)

        config = {
            "tag": "trojan-in",
            "port": port,
            "protocol": "trojan",
            "settings": {
                "clients": [{
                    "password": password
                }]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {
                    "certificates": [{
                        "certificateFile": cert_file,
                        "keyFile": key_file
                    }],
                    "alpn": ["h2", "http/1.1"]
                }
            },
            "sniffing": {
                "enabled": True,
                "destOverride": ["http", "tls"]
            }
        }

        return {
            "inbound": config,
            "password": password
        }

    def generate_vpngate_outbound(
        self,
        tag: str,
        socks_address: str = "127.0.0.1",
        socks_port: int = 1080
    ) -> Dict:
        """
        生成 VPN Gate 出口配置
        通过本地 SOCKS5 代理连接
        """
        return {
            "tag": tag,
            "protocol": "socks",
            "settings": {
                "servers": [{
                    "address": socks_address,
                    "port": socks_port
                }]
            }
        }

    def generate_full_config(
        self,
        inbound_config: Dict,
        outbound_tag: str = "vpngate"
    ) -> Dict:
        """
        生成完整的 Xray 配置文件
        """
        config = {
            "log": {
                "loglevel": "warning"
            },
            "inbounds": [
                inbound_config
            ],
            "outbounds": [
                self.generate_vpngate_outbound(outbound_tag),
                {
                    "tag": "direct",
                    "protocol": "freedom"
                },
                {
                    "tag": "block",
                    "protocol": "blackhole"
                }
            ],
            "routing": {
                "domainStrategy": "AsIs",
                "rules": [
                    {
                        "type": "field",
                        "inboundTag": [inbound_config["tag"]],
                        "outboundTag": outbound_tag
                    }
                ]
            }
        }

        return config


if __name__ == '__main__':
    generator = XrayConfigGenerator()

    print("=== Xray 配置生成器 ===\n")

    print("1. 生成 VLESS + Reality 配置")
    reality_config = generator.generate_vless_reality(
        port=443,
        target_domain='www.microsoft.com:443'
    )
    print(f"   客户端 ID: {reality_config['client_id']}")
    print(f"   公钥: {reality_config['public_key']}")

    print("\n2. 生成完整配置文件")
    full_config = generator.generate_full_config(
        reality_config['inbound']
    )
    print(json.dumps(full_config, indent=2))
