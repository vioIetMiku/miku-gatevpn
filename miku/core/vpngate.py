#!/usr/bin/env python3
"""
VPN Gate API client for fetching and managing VPN servers
"""
import base64
import csv
import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Set
from io import StringIO

import requests


logger = logging.getLogger(__name__)


@dataclass
class VPNServer:
    """VPN Gate server information"""
    hostname: str
    ip: str
    score: int
    ping: int
    speed: int
    country_long: str
    country_short: str
    num_vpn_sessions: int
    uptime: int
    total_users: int
    total_traffic: int
    logtype: str
    operator: str
    message: str
    config_data: str  # Base64 encoded OpenVPN config

    def __str__(self):
        return f"{self.country_short} - {self.ip} (Score: {self.score}, Ping: {self.ping}ms)"


class VPNGateClient:
    """Client for VPN Gate API"""

    API_URL = "https://www.vpngate.net/api/iphone/"
    MIRROR_URLS = [
        "http://vpngate.net/api/iphone/",
        "https://vpngate.jp/api/iphone/",
    ]

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def fetch_servers(self, use_mirror: bool = False) -> List[VPNServer]:
        """
        Fetch server list from VPN Gate API

        Args:
            use_mirror: Try mirror URLs if main API fails

        Returns:
            List of VPNServer objects
        """
        urls = [self.API_URL] + (self.MIRROR_URLS if use_mirror else [])

        for url in urls:
            try:
                logger.info(f"Fetching server list from {url}")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()

                servers = self._parse_csv(response.text)
                logger.info(f"Successfully fetched {len(servers)} servers")
                return servers

            except Exception as e:
                logger.warning(f"Failed to fetch from {url}: {e}")
                continue

        raise RuntimeError("Failed to fetch server list from all sources")

    def _parse_csv(self, csv_data: str) -> List[VPNServer]:
        """Parse CSV data from VPN Gate API"""
        servers = []

        # Skip header lines (starts with #)
        lines = [line for line in csv_data.split('\n') if line and not line.startswith('#')]

        if not lines:
            return servers

        reader = csv.reader(StringIO('\n'.join(lines)))
        next(reader)  # Skip column headers

        for row in reader:
            if len(row) < 15:
                continue

            try:
                server = VPNServer(
                    hostname=row[0],
                    ip=row[1],
                    score=int(row[2]) if row[2] else 0,
                    ping=int(row[3]) if row[3] else 999999,
                    speed=int(row[4]) if row[4] else 0,
                    country_long=row[5],
                    country_short=row[6],
                    num_vpn_sessions=int(row[7]) if row[7] else 0,
                    uptime=int(row[8]) if row[8] else 0,
                    total_users=int(row[9]) if row[9] else 0,
                    total_traffic=int(row[10]) if row[10] else 0,
                    logtype=row[11],
                    operator=row[12],
                    message=row[13],
                    config_data=row[14]
                )

                # Filter out servers without config
                if server.config_data:
                    servers.append(server)

            except (ValueError, IndexError) as e:
                logger.debug(f"Skipping invalid row: {e}")
                continue

        return servers

    def get_best_server(
        self,
        country: str,
        exclude_ips: Optional[Set[str]] = None,
        min_score: int = 100,
        max_sessions: int = 1000
    ) -> Optional[VPNServer]:
        """
        Get the best server for a specific country

        Args:
            country: Two-letter country code (e.g., 'JP', 'US')
            exclude_ips: Set of IP addresses to exclude
            min_score: Minimum server score
            max_sessions: Maximum active sessions

        Returns:
            Best matching VPNServer or None
        """
        exclude_ips = exclude_ips or set()
        servers = self.fetch_servers(use_mirror=True)

        # Filter by country
        candidates = [s for s in servers if s.country_short.upper() == country.upper()]

        if not candidates:
            logger.warning(f"No servers found for country: {country}")
            return None

        # Apply filters
        candidates = [
            s for s in candidates
            if s.ip not in exclude_ips
            and s.score >= min_score
            and s.num_vpn_sessions < max_sessions
        ]

        if not candidates:
            logger.warning(f"No suitable servers found for {country} after filtering")
            # Retry with relaxed filters
            candidates = [
                s for s in servers
                if s.country_short.upper() == country.upper()
                and s.ip not in exclude_ips
            ]

        if not candidates:
            return None

        # Sort by score (higher is better) and ping (lower is better)
        candidates.sort(key=lambda s: (-s.score, s.ping))

        best = candidates[0]
        logger.info(f"Selected server: {best}")
        return best

    def parse_ovpn_config(self, server: VPNServer) -> str:
        """
        Decode and return OpenVPN configuration

        Args:
            server: VPNServer object

        Returns:
            OpenVPN configuration string
        """
        try:
            config = base64.b64decode(server.config_data).decode('utf-8')
            return config
        except Exception as e:
            raise ValueError(f"Failed to decode OpenVPN config: {e}")

    def get_available_countries(self) -> List[tuple]:
        """
        Get list of available countries with server counts

        Returns:
            List of (country_code, country_name, count) tuples
        """
        servers = self.fetch_servers(use_mirror=True)

        countries = {}
        for server in servers:
            code = server.country_short
            if code not in countries:
                countries[code] = {
                    'name': server.country_long,
                    'count': 0
                }
            countries[code]['count'] += 1

        result = [
            (code, info['name'], info['count'])
            for code, info in sorted(countries.items())
        ]

        return result


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    client = VPNGateClient()

    # List available countries
    print("Available countries:")
    for code, name, count in client.get_available_countries():
        print(f"  {code} - {name} ({count} servers)")

    # Get best server for Japan
    print("\nFetching best server for Japan...")
    server = client.get_best_server('JP')
    if server:
        print(f"Found: {server}")
        config = client.parse_ovpn_config(server)
        print(f"Config size: {len(config)} bytes")
