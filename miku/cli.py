#!/usr/bin/env python3
"""
Command-line interface for Miku VPN Gate
"""
import sys
import os
import logging
import signal
from typing import Optional

import click

from miku.manager import MikuManager, MikuConfig


# Setup logging
def setup_logging(level: str = "INFO"):
    """Configure logging"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/var/log/miku/miku.log')
        ]
    )


@click.group()
@click.version_option(version='1.0.0')
def cli():
    """
    Miku VPN Gate - Multi-exit VPN proxy pool manager

    Example usage:

        miku start JP US KR          # Start with Japan, USA, Korea
        miku status                  # Show tunnel status
        miku replace JP              # Replace Japan tunnel
        miku stop                    # Stop all tunnels
    """
    pass


@cli.command()
@click.argument('countries', nargs=-1, required=True)
@click.option('--port', default=7928, help='Base proxy port (default: 7928)')
@click.option('--daemon', '-d', is_flag=True, help='Run in background')
@click.option('--log-level', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Log level')
def start(countries, port, daemon, log_level):
    """
    Start Miku VPN Gate service

    COUNTRIES: List of country codes (e.g., JP US KR)

    Examples:

        miku start JP US             # Japan on 7928, USA on 7929
        miku start JP US KR --port 8000  # Custom base port
    """
    setup_logging(log_level)
    logger = logging.getLogger(__name__)

    # Validate countries
    country_list = [c.upper() for c in countries]

    click.echo(f"Starting Miku with countries: {', '.join(country_list)}")
    click.echo(f"Base port: {port}")

    # Create config
    config = MikuConfig(
        countries=country_list,
        base_port=port,
        data_dir="/var/lib/miku",
        log_dir="/var/log/miku"
    )

    # Create manager
    manager = MikuManager(config)

    try:
        # Start manager
        manager.start()

        if daemon:
            # Daemonize (simplified - production should use proper daemon)
            click.echo("Running in background...")
            # TODO: Proper daemonization
        else:
            click.echo("\nMiku is running. Press Ctrl+C to stop.\n")

            # Setup signal handlers
            def signal_handler(sig, frame):
                click.echo("\n\nShutting down...")
                manager.stop()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Keep running
            import time
            while manager.running:
                time.sleep(1)

    except Exception as e:
        logger.error(f"Failed to start: {e}")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def status():
    """
    Show status of all tunnels

    Displays current tunnel information including:
    - Country and port
    - Server and exit IPs
    - Connection status
    """
    # TODO: Connect to running manager via IPC/socket
    # For now, read from database

    from miku.manager import DatabaseManager

    db_path = "/var/lib/miku/miku.db"

    if not os.path.exists(db_path):
        click.echo("Error: Miku is not running or database not found", err=True)
        sys.exit(1)

    db = DatabaseManager(db_path)

    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT country, port, server_ip, exit_ip, status
            FROM tunnels
            ORDER BY country
        """)

        tunnels = cursor.fetchall()

        if not tunnels:
            click.echo("No tunnels found")
            return

        click.echo("\n" + "="*70)
        click.echo("Miku VPN Gate - Status")
        click.echo("="*70)

        for country, port, server_ip, exit_ip, status in tunnels:
            click.echo(f"\n{country}:")
            click.echo(f"  Port:       {port}")
            click.echo(f"  Server IP:  {server_ip}")
            click.echo(f"  Exit IP:    {exit_ip or 'N/A'}")
            click.echo(f"  Status:     {status}")

        click.echo("\n" + "="*70)
        click.echo(f"Total tunnels: {len(tunnels)}")
        click.echo("="*70 + "\n")

        # Show proxy usage examples
        click.echo("Proxy usage:")
        for country, port, _, _, _ in tunnels:
            click.echo(f"  curl -x socks5h://localhost:{port} https://api.ipify.org  # {country}")
        click.echo()

    finally:
        db.close()


@cli.command()
@click.argument('country')
def replace(country):
    """
    Replace a tunnel with a new server

    COUNTRY: Country code of tunnel to replace (e.g., JP)

    Example:

        miku replace JP    # Get a new Japan server
    """
    country = country.upper()

    click.echo(f"Replacing tunnel for {country}...")

    # TODO: Send command to running manager
    click.echo("Error: This feature requires manager IPC (not yet implemented)", err=True)
    click.echo("Workaround: Restart miku with desired countries", err=True)
    sys.exit(1)


@cli.command()
@click.argument('country')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def test(country, verbose):
    """
    Test a tunnel connection

    COUNTRY: Country code to test (e.g., JP)

    Example:

        miku test JP       # Test Japan tunnel
        miku test JP -v    # Verbose output
    """
    country = country.upper()

    from miku.manager import DatabaseManager

    db_path = "/var/lib/miku/miku.db"

    if not os.path.exists(db_path):
        click.echo("Error: Miku is not running", err=True)
        sys.exit(1)

    db = DatabaseManager(db_path)

    try:
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT port FROM tunnels WHERE country = ?
        """, (country,))

        result = cursor.fetchone()

        if not result:
            click.echo(f"Error: No tunnel found for {country}", err=True)
            sys.exit(1)

        port = result[0]

        click.echo(f"Testing {country} tunnel on port {port}...")

        import subprocess

        # Test connection
        cmd = [
            'curl', '-x', f'socks5h://localhost:{port}',
            '--max-time', '10',
            '-s', 'https://api.ipify.org'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            ip = result.stdout.strip()
            click.echo(f"✓ Success! Exit IP: {ip}")

            if verbose:
                # Get country info
                cmd2 = [
                    'curl', '-x', f'socks5h://localhost:{port}',
                    '--max-time', '10',
                    '-s', f'https://ipapi.co/{ip}/json/'
                ]
                result2 = subprocess.run(cmd2, capture_output=True, text=True)
                if result2.returncode == 0:
                    click.echo(f"\nDetails:\n{result2.stdout}")
        else:
            click.echo(f"✗ Failed: {result.stderr}", err=True)
            sys.exit(1)

    finally:
        db.close()


@cli.command()
def stop():
    """
    Stop Miku service

    Gracefully shuts down all tunnels and cleans up resources.
    """
    click.echo("Stopping Miku...")

    # TODO: Send stop signal to running manager
    click.echo("Error: This feature requires manager IPC (not yet implemented)", err=True)
    click.echo("Workaround: Use 'systemctl stop miku' or kill the process", err=True)
    sys.exit(1)


@cli.command()
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.option('--lines', '-n', default=50, help='Number of lines to show')
def logs(follow, lines):
    """
    View Miku logs

    Examples:

        miku logs              # Show last 50 lines
        miku logs -n 100       # Show last 100 lines
        miku logs -f           # Follow logs in real-time
    """
    log_file = "/var/log/miku/miku.log"

    if not os.path.exists(log_file):
        click.echo("Error: Log file not found", err=True)
        sys.exit(1)

    import subprocess

    if follow:
        # Follow logs
        subprocess.run(['tail', '-f', log_file])
    else:
        # Show last N lines
        subprocess.run(['tail', '-n', str(lines), log_file])


@cli.command()
def web():
    """
    Open Web UI in browser

    Opens the management interface at http://localhost:8787
    """
    import webbrowser

    url = "http://localhost:8787"
    click.echo(f"Opening {url} in browser...")

    webbrowser.open(url)


@cli.command()
def countries():
    """
    List available countries from VPN Gate

    Shows all countries with available VPN servers.
    """
    from miku.core.vpngate import VPNGateClient

    click.echo("Fetching available countries from VPN Gate...")

    try:
        client = VPNGateClient()
        country_list = client.get_available_countries()

        click.echo("\n" + "="*60)
        click.echo("Available Countries")
        click.echo("="*60 + "\n")

        for code, name, count in country_list:
            click.echo(f"  {code:3s} - {name:30s} ({count:3d} servers)")

        click.echo("\n" + "="*60)
        click.echo(f"Total: {len(country_list)} countries")
        click.echo("="*60 + "\n")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    """Main entry point"""
    try:
        cli()
    except Exception as e:
        click.echo(f"Fatal error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
