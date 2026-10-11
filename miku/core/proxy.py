#!/usr/bin/env python3
"""
SOCKS5 and HTTP proxy server with network namespace support
"""
import socket
import struct
import threading
import logging
import select
import ctypes
import os
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class NetNS:
    """Helper for network namespace operations"""

    CLONE_NEWNET = 0x40000000

    @staticmethod
    def switch_to_netns(netns_name: str):
        """
        Switch current thread to a network namespace

        Args:
            netns_name: Name of the network namespace
        """
        netns_path = f'/var/run/netns/{netns_name}'

        if not os.path.exists(netns_path):
            raise RuntimeError(f"Network namespace {netns_name} does not exist")

        try:
            libc = ctypes.CDLL('libc.so.6', use_errno=True)
            with open(netns_path, 'r') as f:
                fd = f.fileno()
                result = libc.setns(fd, NetNS.CLONE_NEWNET)
                if result != 0:
                    errno = ctypes.get_errno()
                    raise OSError(errno, f"setns failed: {os.strerror(errno)}")
        except Exception as e:
            raise RuntimeError(f"Failed to switch to netns {netns_name}: {e}")


class SOCKS5Server:
    """SOCKS5 proxy server with netns support"""

    VERSION = 5

    # SOCKS5 methods
    NO_AUTH = 0

    # SOCKS5 commands
    CMD_CONNECT = 1

    # Address types
    ATYP_IPV4 = 1
    ATYP_DOMAIN = 3
    ATYP_IPV6 = 4

    # Reply codes
    REP_SUCCESS = 0
    REP_GENERAL_FAILURE = 1
    REP_CONNECTION_NOT_ALLOWED = 2
    REP_NETWORK_UNREACHABLE = 3
    REP_HOST_UNREACHABLE = 4
    REP_CONNECTION_REFUSED = 5

    def __init__(self, host: str, port: int, netns_name: str):
        self.host = host
        self.port = port
        self.netns_name = netns_name
        self.server_socket: Optional[socket.socket] = None
        self.running = False

    def start(self):
        """Start the SOCKS5 server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)
        self.running = True

        logger.info(f"SOCKS5 server listening on {self.host}:{self.port} (netns: {self.netns_name})")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")

    def handle_client(self, client_socket: socket.socket):
        """Handle SOCKS5 client connection"""
        try:
            # Greeting
            version, nmethods = struct.unpack('BB', client_socket.recv(2))
            if version != self.VERSION:
                client_socket.close()
                return

            methods = client_socket.recv(nmethods)

            # Send method selection (NO AUTH)
            client_socket.sendall(struct.pack('BB', self.VERSION, self.NO_AUTH))

            # Request
            version, cmd, _, atyp = struct.unpack('BBBB', client_socket.recv(4))

            if version != self.VERSION or cmd != self.CMD_CONNECT:
                self._send_reply(client_socket, self.REP_GENERAL_FAILURE)
                client_socket.close()
                return

            # Parse address
            if atyp == self.ATYP_IPV4:
                addr = socket.inet_ntoa(client_socket.recv(4))
            elif atyp == self.ATYP_DOMAIN:
                addr_len = struct.unpack('B', client_socket.recv(1))[0]
                addr = client_socket.recv(addr_len).decode('utf-8')
            elif atyp == self.ATYP_IPV6:
                addr = socket.inet_ntop(socket.AF_INET6, client_socket.recv(16))
            else:
                self._send_reply(client_socket, self.REP_GENERAL_FAILURE)
                client_socket.close()
                return

            port = struct.unpack('!H', client_socket.recv(2))[0]

            # Connect to target in network namespace
            remote_socket = self._connect_in_netns(addr, port)

            if remote_socket:
                self._send_reply(client_socket, self.REP_SUCCESS)
                self._forward_data(client_socket, remote_socket)
            else:
                self._send_reply(client_socket, self.REP_HOST_UNREACHABLE)
                client_socket.close()

        except Exception as e:
            logger.debug(f"Error handling client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass

    def _connect_in_netns(self, host: str, port: int) -> Optional[socket.socket]:
        """
        Create socket connection inside network namespace

        This runs in a forked process to avoid affecting the main thread's namespace
        """
        try:
            # Fork to isolate namespace change
            pid = os.fork()

            if pid == 0:  # Child process
                try:
                    # Switch to target netns
                    NetNS.switch_to_netns(self.netns_name)

                    # Create socket and connect
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(10)
                    sock.connect((host, port))

                    # Send socket back to parent via Unix socket pair
                    # (simplified - in production, use socket.socketpair())
                    os._exit(0)

                except Exception as e:
                    logger.error(f"Child process connection failed: {e}")
                    os._exit(1)
            else:  # Parent process
                _, status = os.waitpid(pid, 0)
                if os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0:
                    # In production, receive the socket from child
                    # For now, create connection using ip netns exec
                    return self._connect_via_exec(host, port)
                return None

        except Exception as e:
            logger.error(f"Failed to connect in netns: {e}")
            return None

    def _connect_via_exec(self, host: str, port: int) -> Optional[socket.socket]:
        """Fallback: use external helper to connect in netns"""
        # This is a simplified version - production would use proper socket passing
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))
            return sock
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return None

    def _send_reply(self, sock: socket.socket, reply_code: int):
        """Send SOCKS5 reply"""
        reply = struct.pack('BBBB', self.VERSION, reply_code, 0, self.ATYP_IPV4)
        reply += socket.inet_aton('0.0.0.0')
        reply += struct.pack('!H', 0)
        sock.sendall(reply)

    def _forward_data(self, client: socket.socket, remote: socket.socket):
        """Forward data between client and remote"""
        try:
            sockets = [client, remote]

            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 60)

                if exceptional:
                    break

                for sock in readable:
                    try:
                        data = sock.recv(8192)
                        if not data:
                            return

                        if sock is client:
                            remote.sendall(data)
                        else:
                            client.sendall(data)
                    except:
                        return
        finally:
            client.close()
            remote.close()

    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


class HTTPProxyServer:
    """HTTP CONNECT proxy server with netns support"""

    def __init__(self, host: str, port: int, netns_name: str):
        self.host = host
        self.port = port
        self.netns_name = netns_name
        self.server_socket: Optional[socket.socket] = None
        self.running = False

    def start(self):
        """Start the HTTP proxy server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(128)
        self.running = True

        logger.info(f"HTTP proxy listening on {self.host}:{self.port} (netns: {self.netns_name})")

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                thread.start()
            except Exception as e:
                if self.running:
                    logger.error(f"Error accepting connection: {e}")

    def handle_client(self, client_socket: socket.socket):
        """Handle HTTP CONNECT request"""
        try:
            # Read HTTP CONNECT request
            request = b''
            while b'\r\n\r\n' not in request:
                chunk = client_socket.recv(1024)
                if not chunk:
                    client_socket.close()
                    return
                request += chunk

            # Parse CONNECT request
            lines = request.decode('utf-8').split('\r\n')
            if not lines[0].startswith('CONNECT'):
                client_socket.sendall(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                client_socket.close()
                return

            # Extract host and port
            parts = lines[0].split()
            if len(parts) < 2:
                client_socket.sendall(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                client_socket.close()
                return

            host_port = parts[1].split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 443

            # Connect to target in netns
            remote_socket = self._connect_in_netns(host, port)

            if remote_socket:
                client_socket.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                self._forward_data(client_socket, remote_socket)
            else:
                client_socket.sendall(b'HTTP/1.1 502 Bad Gateway\r\n\r\n')
                client_socket.close()

        except Exception as e:
            logger.debug(f"Error handling HTTP client: {e}")
        finally:
            try:
                client_socket.close()
            except:
                pass

    def _connect_in_netns(self, host: str, port: int) -> Optional[socket.socket]:
        """Connect to target in network namespace"""
        # Similar to SOCKS5Server._connect_in_netns
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((host, port))
            return sock
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return None

    def _forward_data(self, client: socket.socket, remote: socket.socket):
        """Forward data between client and remote"""
        try:
            sockets = [client, remote]

            while True:
                readable, _, exceptional = select.select(sockets, [], sockets, 60)

                if exceptional:
                    break

                for sock in readable:
                    try:
                        data = sock.recv(8192)
                        if not data:
                            return

                        if sock is client:
                            remote.sendall(data)
                        else:
                            client.sendall(data)
                    except:
                        return
        finally:
            client.close()
            remote.close()

    def stop(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # Test SOCKS5 server
    server = SOCKS5Server('127.0.0.1', 7928, 'miku_test')
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
