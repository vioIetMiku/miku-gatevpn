#!/usr/bin/env python3
"""
Main manager for coordinating all components
"""
import logging
import sqlite3
import os
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from miku.core.vpngate import VPNGateClient, VPNServer
from miku.core.tunnel import Tunnel, TunnelConfig
from miku.core.health import HealthChecker

logger = logging.getLogger(__name__)


@dataclass
class MikuConfig:
    """Configuration for Miku manager"""
    countries: List[str]
    base_port: int = 7928
    data_dir: str = "/var/lib/miku"
    log_dir: str = "/var/log/miku"
    health_check_interval: int = 30
    failure_threshold: int = 3


class DatabaseManager:
    """SQLite database manager"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_database()

    def _init_database(self):
        """Initialize database schema"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()

        # Tunnels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tunnels (
                id TEXT PRIMARY KEY,
                country TEXT NOT NULL,
                port INTEGER NOT NULL,
                server_ip TEXT,
                exit_ip TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Blacklist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blacklist (
                server_ip TEXT PRIMARY KEY,
                country TEXT,
                reason TEXT,
                blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Health check history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tunnel_id TEXT,
                success BOOLEAN,
                response_time_ms INTEGER,
                exit_ip TEXT,
                error_message TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Events log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT,
                tunnel_id TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    def save_tunnel(self, tunnel: Tunnel):
        """Save tunnel state to database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO tunnels
            (id, country, port, server_ip, exit_ip, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            tunnel.config.tunnel_id,
            tunnel.config.country,
            tunnel.config.port,
            tunnel.config.server_ip,
            tunnel.exit_ip,
            tunnel.status
        ))
        self.conn.commit()

    def add_to_blacklist(self, server_ip: str, country: str, reason: str):
        """Add server IP to blacklist"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO blacklist (server_ip, country, reason)
            VALUES (?, ?, ?)
        """, (server_ip, country, reason))
        self.conn.commit()
        logger.info(f"Added {server_ip} to blacklist: {reason}")

    def get_blacklist(self, country: str, hours: int = 1) -> List[str]:
        """Get blacklisted IPs for a country"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT server_ip FROM blacklist
            WHERE country = ?
            AND blacklisted_at > datetime('now', '-' || ? || ' hours')
        """, (country, hours))
        return [row[0] for row in cursor.fetchall()]

    def record_health_check(self, tunnel_id: str, success: bool,
                           response_time: int, exit_ip: Optional[str],
                           error: Optional[str]):
        """Record health check result"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO health_checks
            (tunnel_id, success, response_time_ms, exit_ip, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (tunnel_id, success, response_time, exit_ip, error))
        self.conn.commit()

    def log_event(self, event_type: str, tunnel_id: str, details: str):
        """Log system event"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO events (event_type, tunnel_id, details)
            VALUES (?, ?, ?)
        """, (event_type, tunnel_id, details))
        self.conn.commit()

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


class MikuManager:
    """Main manager coordinating all components"""

    def __init__(self, config: MikuConfig):
        self.config = config
        self.vpngate = VPNGateClient()
        self.tunnels: Dict[str, Tunnel] = {}
        self.db = DatabaseManager(
            os.path.join(config.data_dir, "miku.db")
        )
        self.health_checker = HealthChecker(
            check_interval=config.health_check_interval,
            failure_threshold=config.failure_threshold
        )
        self.health_thread: Optional[threading.Thread] = None
        self.running = False

        # Ensure directories exist
        os.makedirs(config.data_dir, exist_ok=True)
        os.makedirs(config.log_dir, exist_ok=True)

    def start(self):
        """Start all components"""
        logger.info("Starting Miku VPN Gate manager")
        self.running = True

        try:
            # Create tunnels for each country
            for idx, country in enumerate(self.config.countries):
                port = self.config.base_port + idx
                logger.info(f"Creating tunnel for {country} on port {port}")

                tunnel = self._create_tunnel(country, port)
                if tunnel:
                    self.tunnels[country] = tunnel
                    self.db.save_tunnel(tunnel)
                    self.db.log_event("TUNNEL_CREATED", country,
                                     f"Port {port}, IP {tunnel.exit_ip}")
                else:
                    logger.error(f"Failed to create tunnel for {country}")

            if not self.tunnels:
                raise RuntimeError("No tunnels created successfully")

            # Start health monitoring
            logger.info("Starting health monitoring")
            self.health_thread = threading.Thread(
                target=self.health_checker.start_monitoring,
                args=(self.tunnels,),
                daemon=True
            )
            self.health_thread.start()

            logger.info(f"Miku started with {len(self.tunnels)} tunnels")
            self._print_status()

        except Exception as e:
            logger.error(f"Failed to start Miku: {e}")
            self.stop()
            raise

    def _create_tunnel(self, country: str, port: int) -> Optional[Tunnel]:
        """Create a tunnel for a specific country"""
        try:
            # Get blacklisted IPs
            blacklist = self.db.get_blacklist(country, hours=2)
            blacklist_set = set(blacklist)

            # Add current failed IPs from health checker
            blacklist_set.update(self.health_checker.get_failed_ips())

            logger.info(f"Fetching server for {country} (excluding {len(blacklist_set)} IPs)")

            # Get best server
            server = self.vpngate.get_best_server(
                country=country,
                exclude_ips=blacklist_set
            )

            if not server:
                logger.error(f"No suitable server found for {country}")
                return None

            # Parse OpenVPN config
            ovpn_config = self.vpngate.parse_ovpn_config(server)

            # Create tunnel config
            tunnel_id = f"{country.lower()}_{int(datetime.now().timestamp())}"
            config = TunnelConfig(
                tunnel_id=tunnel_id,
                country=country,
                port=port,
                server_ip=server.ip,
                ovpn_config=ovpn_config
            )

            # Create tunnel
            tunnel = Tunnel(config)
            success = tunnel.create()

            if success:
                logger.info(f"Tunnel created: {tunnel}")
                return tunnel
            else:
                logger.error(f"Failed to create tunnel for {country}")
                # Add to blacklist
                self.db.add_to_blacklist(
                    server.ip,
                    country,
                    "Failed to establish connection"
                )
                return None

        except Exception as e:
            logger.error(f"Error creating tunnel for {country}: {e}")
            return None

    def replace_tunnel(self, country: str) -> bool:
        """Replace a failed tunnel"""
        logger.info(f"Replacing tunnel for {country}")

        # Get old tunnel
        old_tunnel = self.tunnels.get(country)
        if not old_tunnel:
            logger.error(f"No tunnel found for {country}")
            return False

        port = old_tunnel.config.port

        # Add old server to blacklist
        if old_tunnel.config.server_ip:
            self.db.add_to_blacklist(
                old_tunnel.config.server_ip,
                country,
                "Manual replacement or health check failure"
            )

        # Destroy old tunnel
        try:
            old_tunnel.destroy()
        except Exception as e:
            logger.warning(f"Error destroying old tunnel: {e}")

        # Create new tunnel
        new_tunnel = self._create_tunnel(country, port)

        if new_tunnel:
            self.tunnels[country] = new_tunnel
            self.db.save_tunnel(new_tunnel)
            self.db.log_event("TUNNEL_REPLACED", country,
                            f"Old IP: {old_tunnel.config.server_ip}, "
                            f"New IP: {new_tunnel.exit_ip}")
            logger.info(f"Successfully replaced tunnel for {country}")
            return True
        else:
            logger.error(f"Failed to create replacement tunnel for {country}")
            return False

    def stop(self):
        """Stop all components"""
        logger.info("Stopping Miku manager")
        self.running = False

        # Stop health checker
        if self.health_checker:
            self.health_checker.stop_monitoring()

        # Wait for health thread
        if self.health_thread and self.health_thread.is_alive():
            self.health_thread.join(timeout=5)

        # Destroy all tunnels
        for country, tunnel in list(self.tunnels.items()):
            try:
                logger.info(f"Destroying tunnel for {country}")
                tunnel.destroy()
            except Exception as e:
                logger.error(f"Error destroying tunnel {country}: {e}")

        # Close database
        self.db.close()

        logger.info("Miku stopped")

    def get_status(self) -> Dict:
        """Get current system status"""
        status = {
            "running": self.running,
            "tunnels": [],
            "total_tunnels": len(self.tunnels)
        }

        for country, tunnel in self.tunnels.items():
            tunnel_status = {
                "country": country,
                "port": tunnel.config.port,
                "server_ip": tunnel.config.server_ip,
                "exit_ip": tunnel.exit_ip,
                "status": tunnel.status,
                "netns": tunnel.netns_name
            }
            status["tunnels"].append(tunnel_status)

        return status

    def _print_status(self):
        """Print current status to console"""
        print("\n" + "="*60)
        print("Miku VPN Gate - Status")
        print("="*60)

        for country, tunnel in self.tunnels.items():
            print(f"\n{country.upper()}:")
            print(f"  Port:      {tunnel.config.port}")
            print(f"  Server IP: {tunnel.config.server_ip}")
            print(f"  Exit IP:   {tunnel.exit_ip}")
            print(f"  Status:    {tunnel.status}")

        print("\n" + "="*60)
        print(f"Total tunnels: {len(self.tunnels)}")
        print("="*60 + "\n")


# Example usage
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    config = MikuConfig(
        countries=["JP", "US"],
        base_port=7928
    )

    manager = MikuManager(config)

    try:
        manager.start()

        # Keep running
        import time
        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        print("\nShutting down...")
        manager.stop()
