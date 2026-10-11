#!/usr/bin/env python3
"""
VPN Gate 节点质量检测模块
"""
import subprocess
import time
import json
import re
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed


class NodeQualityChecker:
    """节点质量检测器"""

    def __init__(self):
        self.streaming_services = {
            'Netflix': 'https://www.netflix.com',
            'YouTube': 'https://www.youtube.com',
            'Disney+': 'https://www.disneyplus.com'
        }

    def check_connectivity(self, node_ip: str, timeout: int = 5) -> Tuple[bool, int]:
        """检测节点连通性和延迟"""
        try:
            start = time.time()
            result = subprocess.run(
                ['ping', '-c', '3', '-W', str(timeout), node_ip],
                capture_output=True,
                text=True,
                timeout=timeout + 2
            )
            elapsed = int((time.time() - start) * 1000)

            if result.returncode == 0:
                # 提取平均延迟
                match = re.search(r'avg[^=]*=\s*([\d.]+)', result.stdout)
                if match:
                    avg_ping = int(float(match.group(1)))
                    return True, avg_ping

                return True, elapsed // 3

            return False, -1

        except Exception as e:
            print(f"连通性检测失败: {e}")
            return False, -1

    def get_ip_info(self, ip: str) -> Optional[Dict]:
        """获取IP详细信息（地理位置、ISP、AS号）"""
        try:
            # 使用 ip-api.com
            result = subprocess.run(
                ['curl', '-s', '--max-time', '10',
                 f'http://ip-api.com/json/{ip}?fields=status,country,countryCode,region,city,isp,org,as,asname,mobile,proxy,hosting'],
                capture_output=True,
                text=True,
                timeout=12
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country'),
                        'country_code': data.get('countryCode'),
                        'region': data.get('region'),
                        'city': data.get('city'),
                        'isp': data.get('isp'),
                        'org': data.get('org'),
                        'as': data.get('as'),
                        'asname': data.get('asname'),
                        'is_mobile': data.get('mobile', False),
                        'is_proxy': data.get('proxy', False),
                        'is_hosting': data.get('hosting', False)
                    }

        except Exception as e:
            print(f"IP信息获取失败: {e}")

        return None

    def check_ip_purity(self, ip: str) -> Tuple[str, int]:
        """
        检测IP纯净度
        返回: (类型, 分数)
        类型: residential, mobile, datacenter, proxy
        分数: 0-100
        """
        info = self.get_ip_info(ip)
        if not info:
            return 'unknown', 0

        # 计算纯净度分数
        score = 100

        # 如果是机房IP，大幅降分
        if info.get('is_hosting'):
            return 'datacenter', 20

        # 如果是代理IP，降分
        if info.get('is_proxy'):
            score -= 50

        # 移动IP优先级最高
        if info.get('is_mobile'):
            return 'mobile', 95

        # 住宅IP
        isp_lower = (info.get('isp') or '').lower()
        org_lower = (info.get('org') or '').lower()

        # 住宅关键词
        residential_keywords = ['residential', 'broadband', 'cable', 'fiber', 'dsl', 'home']
        if any(keyword in isp_lower or keyword in org_lower for keyword in residential_keywords):
            return 'residential', 90

        # 商业关键词
        business_keywords = ['business', 'corporate', 'enterprise']
        if any(keyword in isp_lower or keyword in org_lower for keyword in business_keywords):
            return 'business', 70

        # 默认
        return 'residential', score

    def check_streaming(self, proxy_addr: str, service: str = 'Netflix') -> bool:
        """
        通过代理检测流媒体解锁
        proxy_addr: socks5://ip:port 或 http://ip:port
        """
        if service not in self.streaming_services:
            return False

        url = self.streaming_services[service]

        try:
            result = subprocess.run(
                ['curl', '-x', proxy_addr, '-s', '-o', '/dev/null',
                 '-w', '%{http_code}', '--max-time', '10', url],
                capture_output=True,
                text=True,
                timeout=12
            )

            http_code = result.stdout.strip()
            # 200-399 认为可以访问
            return http_code.startswith('2') or http_code.startswith('3')

        except:
            return False

    def comprehensive_check(self, node_ip: str, detailed: bool = True) -> Dict:
        """
        综合检测节点质量
        返回完整的评估报告
        """
        report = {
            'ip': node_ip,
            'connectivity': False,
            'ping': -1,
            'score': 0,
            'rank': '⭐',
            'info': None,
            'purity_type': 'unknown',
            'purity_score': 0
        }

        # 1. 连通性
        is_alive, ping = self.check_connectivity(node_ip)
        report['connectivity'] = is_alive
        report['ping'] = ping

        if not is_alive:
            return report

        # 2. IP详细信息
        if detailed:
            info = self.get_ip_info(node_ip)
            report['info'] = info

            # 3. 纯净度
            purity_type, purity_score = self.check_ip_purity(node_ip)
            report['purity_type'] = purity_type
            report['purity_score'] = purity_score

            # 计算综合评分
            score = 0

            # 延迟评分 (40分)
            if ping < 50:
                score += 40
            elif ping < 100:
                score += 30
            elif ping < 200:
                score += 20
            else:
                score += 10

            # 纯净度评分 (60分)
            score += int(purity_score * 0.6)

            report['score'] = score

            # 评级
            if score >= 90:
                report['rank'] = '⭐⭐⭐⭐⭐'
            elif score >= 80:
                report['rank'] = '⭐⭐⭐⭐'
            elif score >= 70:
                report['rank'] = '⭐⭐⭐'
            elif score >= 60:
                report['rank'] = '⭐⭐'
            else:
                report['rank'] = '⭐'

        return report

    def batch_check(self, node_ips: List[str], max_workers: int = 10) -> List[Dict]:
        """批量检测节点"""
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ip = {
                executor.submit(self.comprehensive_check, ip): ip
                for ip in node_ips
            }

            for future in as_completed(future_to_ip):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    ip = future_to_ip[future]
                    print(f"检测 {ip} 失败: {e}")

        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法: python checker.py <IP地址> [IP地址...]")
        sys.exit(1)

    ips = sys.argv[1:]
    checker = NodeQualityChecker()

    print(f"正在检测 {len(ips)} 个节点...\n")

    if len(ips) == 1:
        # 单个节点详细检测
        result = checker.comprehensive_check(ips[0])
        print(f"IP: {result['ip']}")
        print(f"连通性: {'✓' if result['connectivity'] else '✗'}")
        print(f"延迟: {result['ping']}ms")
        print(f"类型: {result['purity_type']}")
        print(f"纯净度: {result['purity_score']}/100")
        print(f"综合评分: {result['score']}/100 {result['rank']}")

        if result['info']:
            print(f"\n详细信息:")
            print(f"  国家: {result['info']['country']} ({result['info']['country_code']})")
            print(f"  地区: {result['info']['city']}, {result['info']['region']}")
            print(f"  ISP: {result['info']['isp']}")
            print(f"  AS: {result['info']['as']}")

    else:
        # 批量检测
        results = checker.batch_check(ips)

        print("排名  IP地址            延迟    类型        纯净度  评分  评级")
        print("-" * 70)

        for i, r in enumerate(results, 1):
            if r['connectivity']:
                print(f"{i:3d}  {r['ip']:15s}  {r['ping']:4d}ms  "
                      f"{r['purity_type']:10s}  {r['purity_score']:3d}     "
                      f"{r['score']:3d}   {r['rank']}")
            else:
                print(f"{i:3d}  {r['ip']:15s}  离线")
