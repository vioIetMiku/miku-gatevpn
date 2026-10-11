#!/usr/bin/env python3
"""
Health checking and automatic tunnel replacement
"""
import time
import logging
import subprocess
import asyncio
from typing import Dict, Optional, Set
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """Health check result"""
    success: bool
    response_time_ms: int
    exit_ip: Optional[str]
    error_message: Optional[str]
    checked_at: datetime


class HealthChecker:
    """Monitor tunnel health and handle failures"""

    def __init__(self, check_interval: int = 30, failure_threshold: int = 3):
        """
        Args:
            check_interval: Seconds between health checks
            failure_threshold: Consecutive failures before replacement
        """
        self.check_interval = check_interval
        self.failure_threshold = failure_threshold
        self.running = False
        self.tunnels: Dict = {}
        self.failed_ips: Set[str] = set()

    def check_tunnel(self, tunnel) -> HealthStatus:
        """
        Perform health check on a tunnel

        Args:
            tunnel: Tunnel object to check

        Returns:
            HealthStatus with check results
        """
        start_time = time.time()

        try:
            # 1. Check if tunnel is marked as alive
            if not tunnel.is_alive():
                return HealthStatus(
                    success=False,
                    response_time_ms=0,
                    exit_ip=None,
                    error_message="Tunnel is not alive",
                    checked_at=datetime.now()
                )

            # 2. Get current exit IP
            exit_ip = tunnel.get_exit_ip()

            if not exit_ip:
                return HealthStatus(
                    success=False,
                    response_time_ms=int((time.time() - start_time) * 1000),
                    exit_ip=None,
                    error_message="Failed to get exit IP",
                    checked_at=datetime.now()
                )

            # 3. Verify IP hasn't changed unexpectedly
            if tunnel.exit_ip and exit_ip != tunnel.exit_ip:
                logger.warning(
                    f"Tunnel {tunnel.config.tunnel_id} IP changed: "
                    f"{tunnel.exit_ip} -> {exit_ip}"
                )
                tunnel.exit_ip = exit_ip

            response_time = int((time.time() - start_time) * 1000)

            return HealthStatus(
                success=True,
                response_time_ms=response_time,
                exit_ip=exit_ip,
                error_message=None,
                checked_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"Health check exception for {tunnel.config.tunnel_id}: {e}")
            return HealthStatus(
                success=False,
                response_time_ms=int((time.time() - start_time) * 1000),
                exit_ip=None,
                error_message=str(e),
                checked_at=datetime.now()
            )

    def start_monitoring(self, tunnels: Dict):
        """
        Start health monitoring loop

        Args:
            tunnels: Dictionary of tunnel_id -> Tunnel objects
        """
        self.tunnels = tunnels
        self.running = True

        logger.info(f"Starting health monitoring (interval: {self.check_interval}s)")

        while self.running:
            try:
                self._check_all_tunnels()
                time.sleep(self.check_interval)
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Health monitoring loop error: {e}")
                time.sleep(5)

    def _check_all_tunnels(self):
        """Check all tunnels and handle failures"""
        for tunnel_id, tunnel in list(self.tunnels.items()):
            try:
                status = self.check_tunnel(tunnel)

                if status.success:
                    # Reset failure count on success
                    if hasattr(tunnel, 'failure_count'):
                        tunnel.failure_count = 0

                    logger.debug(
                        f"Health check OK for {tunnel_id}: "
                        f"{status.exit_ip} ({status.response_time_ms}ms)"
                    )
                else:
                    # Increment failure count
                    if not hasattr(tunnel, 'failure_count'):
                        tunnel.failure_count = 0
                    tunnel.failure_count += 1

                    logger.warning(
                        f"Health check FAILED for {tunnel_id}: {status.error_message} "
                        f"(failure count: {tunnel.failure_count}/{self.failure_threshold})"
                    )

                    # Trigger replacement if threshold reached
                    if tunnel.failure_count >= self.failure_threshold:
                        logger.error(
                            f"Tunnel {tunnel_id} exceeded failure threshold, "
                            f"needs replacement"
                        )
                        self._handle_tunnel_failure(tunnel)

            except Exception as e:
                logger.error(f"Error checking tunnel {tunnel_id}: {e}")

    def _handle_tunnel_failure(self, tunnel):
        """
        Handle tunnel failure - mark for replacement

        Args:
            tunnel: Failed tunnel object
        """
        # Add server IP to failed list
        if tunnel.config.server_ip:
            self.failed_ips.add(tunnel.config.server_ip)
            logger.info(f"Added {tunnel.config.server_ip} to failed IPs blacklist")

        # Mark tunnel as failed
        tunnel.status = "failed"

        logger.error(
            f"Tunnel {tunnel.config.tunnel_id} marked as failed. "
            f"Automatic replacement should be handled by manager."
        )

    def stop_monitoring(self):
        """Stop health monitoring"""
        self.running = False
        logger.info("Stopping health monitoring")

    def get_failed_ips(self) -> Set[str]:
        """Get set of failed IP addresses"""
        return self.failed_ips.copy()

    def clear_failed_ip(self, ip: str):
        """Remove IP from failed list"""
        self.failed_ips.discard(ip)


# Example usage
if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    from tunnel import Tunnel, TunnelConfig

    # Create a test tunnel
    config = TunnelConfig(
        tunnel_id="test1",
        country="JP",
        port=7928,
        server_ip="219.100.37.82",
        ovpn_config="# Test config"
    )

    tunnel = Tunnel(config)
    tunnels = {"test1": tunnel}

    # Start health checker
    checker = HealthChecker(check_interval=10, failure_threshold=2)

    try:
        checker.start_monitoring(tunnels)
    except KeyboardInterrupt:
        checker.stop_monitoring()
