#!/usr/bin/env python3
"""
Tunnel management with network namespace isolation
"""
import os
import subprocess
import time
import logging
import signal
import tempfile
from typing import Optional
from dataclasses import dataclass

import requests


logger = logging.getLogger(__name__)


@dataclass
class TunnelConfig:
    """Configuration for a VPN tunnel"""
    tunnel_id: str
    country: str
    port: int
    server_ip: str
    ovpn_config: str


class Tunnel:
    """Manages a single VPN tunnel with network namespace isolation"""

    def __init__(self, config: TunnelConfig):
        self.config = config
        self.netns_name = f"miku_{config.tunnel_id}"
        self.ovpn_process: Optional[subprocess.Popen] = None
        self.config_file: Optional[str] = None
        self.exit_ip: Optional[str] = None
        self.status = "stopped"

    def create(self) -> bool:
        """
        Create network namespace and start OpenVPN tunnel

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Creating tunnel {self.config.tunnel_id} for {self.config.country}")

            # Create network namespace
            if not self._create_netns():
                return False

            # Write OpenVPN config to temporary file
            self.config_file = self._write_config()

            # Start OpenVPN in the namespace
            if not self._start_openvpn():
                self.destroy()
                return False

            # Wait for connection and get exit IP
            if not self._wait_for_connection():
                self.destroy()
                return False

            self.status = "running"
            logger.info(f"Tunnel {self.config.tunnel_id} created successfully, exit IP: {self.exit_ip}")
            return True

        except Exception as e:
            logger.error(f"Failed to create tunnel {self.config.tunnel_id}: {e}")
            self.destroy()
            return False

    def _create_netns(self) -> bool:
        """Create network namespace and configure routing"""
        try:
            # Check if namespace already exists
            result = subprocess.run(
                ['ip', 'netns', 'list'],
                capture_output=True,
                text=True
            )
            if self.netns_name in result.stdout:
                logger.warning(f"Namespace {self.netns_name} already exists, deleting it")
                self._delete_netns()

            # Create namespace
            subprocess.run(
                ['ip', 'netns', 'add', self.netns_name],
                check=True,
                capture_output=True
            )

            # Bring up loopback interface inside namespace
            subprocess.run(
                ['ip', 'netns', 'exec', self.netns_name, 'ip', 'link', 'set', 'lo', 'up'],
                check=True,
                capture_output=True
            )

            logger.debug(f"Created network namespace: {self.netns_name}")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create netns: {e}")
            return False

    def _delete_netns(self):
        """Delete network namespace"""
        try:
            subprocess.run(
                ['ip', 'netns', 'delete', self.netns_name],
                check=True,
                capture_output=True,
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to delete netns {self.netns_name}: {e}")

    def _write_config(self) -> str:
        """Write OpenVPN config to temporary file"""
        fd, path = tempfile.mkstemp(suffix='.ovpn', prefix=f'miku_{self.config.tunnel_id}_')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(self.config.ovpn_config)
            os.chmod(path, 0o600)
            return path
        except Exception as e:
            os.close(fd)
            raise e

    def _start_openvpn(self) -> bool:
        """Start OpenVPN process inside network namespace"""
        try:
            # OpenVPN command
            cmd = [
                'ip', 'netns', 'exec', self.netns_name,
                'openvpn',
                '--config', self.config_file,
                '--daemon',
                '--writepid', f'/tmp/miku_{self.config.tunnel_id}.pid',
                '--log', f'/var/log/miku/tunnel_{self.config.tunnel_id}.log',
                '--verb', '3'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode != 0:
                logger.error(f"OpenVPN failed to start: {result.stderr}")
                return False

            # Read PID
            time.sleep(2)  # Give OpenVPN time to write PID file
            pid_file = f'/tmp/miku_{self.config.tunnel_id}.pid'
            if os.path.exists(pid_file):
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    # Verify process is running
                    try:
                        os.kill(pid, 0)
                        logger.debug(f"OpenVPN started with PID {pid}")
                    except OSError:
                        logger.error(f"OpenVPN process {pid} not found")
                        return False
            else:
                logger.warning("PID file not found, but continuing")

            return True

        except Exception as e:
            logger.error(f"Failed to start OpenVPN: {e}")
            return False

    def _wait_for_connection(self, timeout: int = 30) -> bool:
        """
        Wait for VPN connection to establish and get exit IP

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if connected successfully
        """
        logger.info(f"Waiting for VPN connection (timeout: {timeout}s)")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Check if tun0 interface exists in namespace
                result = subprocess.run(
                    ['ip', 'netns', 'exec', self.netns_name, 'ip', 'link', 'show', 'tun0'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    # tun0 exists, try to get exit IP
                    exit_ip = self.get_exit_ip()
                    if exit_ip:
                        self.exit_ip = exit_ip
                        logger.info(f"VPN connected! Exit IP: {exit_ip}")
                        return True

            except Exception as e:
                logger.debug(f"Connection check failed: {e}")

            time.sleep(2)

        logger.error(f"VPN connection timeout after {timeout}s")
        return False

    def get_exit_ip(self) -> Optional[str]:
        """
        Get current exit IP address of the tunnel

        Returns:
            IP address string or None if failed
        """
        services = [
            'https://ifconfig.me',
            'https://api.ipify.org',
            'https://icanhazip.com'
        ]

        for service in services:
            try:
                result = subprocess.run(
                    ['ip', 'netns', 'exec', self.netns_name,
                     'curl', '-s', '--max-time', '10', service],
                    capture_output=True,
                    text=True,
                    timeout=15
                )

                if result.returncode == 0 and result.stdout.strip():
                    ip = result.stdout.strip()
                    # Basic IP validation
                    parts = ip.split('.')
                    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                        return ip

            except Exception as e:
                logger.debug(f"Failed to get IP from {service}: {e}")
                continue

        return None

    def is_alive(self) -> bool:
        """Check if tunnel is alive"""
        try:
            # Check if namespace exists
            result = subprocess.run(
                ['ip', 'netns', 'list'],
                capture_output=True,
                text=True
            )
            if self.netns_name not in result.stdout:
                return False

            # Check if can get exit IP
            current_ip = self.get_exit_ip()
            if not current_ip:
                return False

            # Optionally verify IP hasn't changed
            if self.exit_ip and current_ip != self.exit_ip:
                logger.warning(f"Exit IP changed: {self.exit_ip} -> {current_ip}")
                self.exit_ip = current_ip

            return True

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def destroy(self):
        """Clean up tunnel resources"""
        logger.info(f"Destroying tunnel {self.config.tunnel_id}")

        # Kill OpenVPN process
        pid_file = f'/tmp/miku_{self.config.tunnel_id}.pid'
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.remove(pid_file)
            except Exception as e:
                logger.warning(f"Failed to kill OpenVPN process: {e}")

        # Delete network namespace
        self._delete_netns()

        # Remove config file
        if self.config_file and os.path.exists(self.config_file):
            try:
                os.remove(self.config_file)
            except Exception as e:
                logger.warning(f"Failed to remove config file: {e}")

        self.status = "stopped"
        logger.info(f"Tunnel {self.config.tunnel_id} destroyed")

    def __str__(self):
        return (f"Tunnel(id={self.config.tunnel_id}, country={self.config.country}, "
                f"port={self.config.port}, exit_ip={self.exit_ip}, status={self.status})")


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # This is just for testing - in real usage, get config from vpngate.py
    test_config = TunnelConfig(
        tunnel_id="test1",
        country="JP",
        port=7928,
        server_ip="219.100.37.82",
        ovpn_config="# OpenVPN config would go here"
    )

    tunnel = Tunnel(test_config)
    print(f"Creating tunnel: {tunnel}")

    # Note: This will fail without a valid OpenVPN config
    # success = tunnel.create()
    # print(f"Creation {'succeeded' if success else 'failed'}")
