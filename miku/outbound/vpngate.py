#!/usr/bin/env python3
"""
VPN Gate API 客户端
获取和解析 VPN Gate 节点列表
"""
import requests
import base64
import csv
from typing import List, Dict, Optional
from io import StringIO


class VPNGateClient:
    """VPN Gate API 客户端"""

    API_URL = "https://www.vpngate.net/api/iphone/"
    MIRROR_URLS = [
        "https://www.vpngate.net/api/iphone/",
        "https://vpngate.mirror.example.com/api/iphone/"  # 备用镜像
    ]

    def __init__(self):
        self.nodes = []

    def fetch_nodes(self, timeout: int = 30) -> List[Dict]:
        """
        从 VPN Gate API 获取节点列表
        返回解析后的节点列表
        """
        for url in self.MIRROR_URLS:
            try:
                response = requests.get(url, timeout=timeout)
                if response.status_code == 200:
                    self.nodes = self._parse_csv(response.text)
                    return self.nodes
            except Exception as e:
                print(f"从 {url} 获取失败: {e}")
                continue

        raise Exception("无法从任何镜像获取节点列表")

    def _parse_csv(self, csv_text: str) -> List[Dict]:
        """解析 CSV 格式的节点列表"""
        nodes = []

        # 跳过开头的注释行
        lines = csv_text.strip().split('\n')
        csv_start = 0
        for i, line in enumerate(lines):
            if line.startswith('#HostName'):
                csv_start = i
                break

        csv_data = '\n'.join(lines[csv_start:])
        reader = csv.DictReader(StringIO(csv_data))

        for row in reader:
            try:
                # 解析 OpenVPN 配置
                ovpn_config = base64.b64decode(
                    row.get('OpenVPN_ConfigData_Base64', '')
                ).decode('utf-8')

                node = {
                    'hostname': row.get('HostName', ''),
                    'ip': row.get('IP', ''),
                    'country': row.get('CountryLong', ''),
                    'country_code': row.get('CountryShort', ''),
                    'ping': int(row.get('Ping', 0)),
                    'speed': int(row.get('Speed', 0)),
                    'sessions': int(row.get('NumVpnSessions', 0)),
                    'uptime': int(row.get('Uptime', 0)),
                    'score': int(row.get('Score', 0)),
                    'logtype': row.get('LogType', ''),
                    'operator': row.get('Operator', ''),
                    'message': row.get('Message', ''),
                    'ovpn_config': ovpn_config
                }

                # 计算综合评分
                node['quality_score'] = self._calculate_quality(node)

                nodes.append(node)

            except Exception as e:
                print(f"解析节点失败: {e}")
                continue

        return nodes

    def _calculate_quality(self, node: Dict) -> float:
        """
        计算节点质量评分
        考虑因素：速度、延迟、会话数、在线时间
        """
        score = 0.0

        # 速度评分 (40%)
        speed_mbps = node['speed'] / 1_000_000
        if speed_mbps >= 50:
            score += 40
        elif speed_mbps >= 20:
            score += 30
        elif speed_mbps >= 10:
            score += 20
        else:
            score += 10

        # 延迟评分 (30%)
        ping = node['ping']
        if ping <= 50:
            score += 30
        elif ping <= 100:
            score += 25
        elif ping <= 200:
            score += 15
        else:
            score += 5

        # 负载评分 (20%)
        sessions = node['sessions']
        if sessions <= 10:
            score += 20
        elif sessions <= 50:
            score += 15
        elif sessions <= 100:
            score += 10
        else:
            score += 5

        # 稳定性评分 (10%)
        uptime_hours = node['uptime'] / 3600
        if uptime_hours >= 168:  # 7天
            score += 10
        elif uptime_hours >= 24:
            score += 7
        else:
            score += 3

        return score

    def filter_by_country(self, country_code: str) -> List[Dict]:
        """按国家代码筛选节点"""
        return [
            node for node in self.nodes
            if node['country_code'].upper() == country_code.upper()
        ]

    def get_best_nodes(self, country_code: str, limit: int = 10) -> List[Dict]:
        """获取指定国家的最佳节点"""
        country_nodes = self.filter_by_country(country_code)

        # 按质量评分排序
        country_nodes.sort(key=lambda x: x['quality_score'], reverse=True)

        return country_nodes[:limit]

    def is_residential(self, node: Dict) -> bool:
        """
        简单判断是否为住宅IP节点
        基于 hostname 和 IP 段
        """
        hostname = node['hostname'].lower()
        ip = node['ip']

        # VPN Gate 官方服务器排除
        if hostname.startswith('public-vpn-'):
            return False

        # 官方机房段排除
        if ip.startswith('219.100.37.'):
            return False

        return True

    def get_available_countries(self) -> List[tuple]:
        """获取所有可用国家列表"""
        countries = {}

        for node in self.nodes:
            code = node['country_code']
            name = node['country']

            if code not in countries:
                countries[code] = {'name': name, 'count': 0}

            countries[code]['count'] += 1

        # 转换为列表并排序
        result = [
            (code, info['name'], info['count'])
            for code, info in countries.items()
        ]

        result.sort(key=lambda x: x[2], reverse=True)
        return result


if __name__ == '__main__':
    import sys

    client = VPNGateClient()

    print("正在从 VPN Gate 获取节点列表...\n")

    try:
        nodes = client.fetch_nodes()
        print(f"✅ 成功获取 {len(nodes)} 个节点\n")

        if len(sys.argv) > 1:
            # 显示指定国家的节点
            country = sys.argv[1].upper()
            best_nodes = client.get_best_nodes(country, 10)

            print(f"=== {country} 最佳节点 ===\n")

            for i, node in enumerate(best_nodes, 1):
                residential = "🏠 住宅" if client.is_residential(node) else "🏢 机房"
                print(f"{i:2d}. {node['ip']:15s} {residential}")
                print(f"    延迟: {node['ping']:4d}ms  速度: {node['speed']//1_000_000:3d}Mbps")
                print(f"    会话: {node['sessions']:3d}    评分: {node['quality_score']:.1f}/100")
                print(f"    运营: {node['operator'][:30]}")
                print()

        else:
            # 显示国家列表
            countries = client.get_available_countries()

            print("=== 可用国家 ===\n")
            print("代码  国家名称                        节点数")
            print("-" * 50)

            for code, name, count in countries[:20]:
                print(f"{code:4s}  {name:30s}  {count:3d}")

    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)
