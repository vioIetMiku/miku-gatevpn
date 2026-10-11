#!/usr/bin/env python3
"""
Flask Web API for Miku management
"""
import logging
from flask import Flask, jsonify, request, render_template_string
from miku.manager import DatabaseManager

logger = logging.getLogger(__name__)

app = Flask(__name__)


# Simple HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Miku VPN Gate</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; margin-bottom: 20px; }
        .tunnel-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .tunnel-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .tunnel-card h2 {
            color: #007bff;
            margin-bottom: 15px;
            font-size: 24px;
        }
        .tunnel-info { margin: 10px 0; }
        .tunnel-info strong { color: #666; display: inline-block; width: 100px; }
        .status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }
        .status.running { background: #28a745; color: white; }
        .status.failed { background: #dc3545; color: white; }
        .status.stopped { background: #6c757d; color: white; }
        .btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-top: 10px;
        }
        .btn:hover { background: #0056b3; }
        .proxy-example {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            margin-top: 20px;
            font-family: monospace;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Miku VPN Gate</h1>

        <div id="tunnels" class="tunnel-grid"></div>

        <div class="proxy-example">
            <strong>Proxy Usage:</strong><br>
            <code>curl -x socks5h://localhost:PORT https://api.ipify.org</code>
        </div>
    </div>

    <script>
        async function loadTunnels() {
            try {
                const response = await fetch('/api/tunnels');
                const tunnels = await response.json();

                const container = document.getElementById('tunnels');
                container.innerHTML = tunnels.map(t => `
                    <div class="tunnel-card">
                        <h2>${t.country}</h2>
                        <div class="tunnel-info">
                            <strong>Port:</strong> ${t.port}
                        </div>
                        <div class="tunnel-info">
                            <strong>Server IP:</strong> ${t.server_ip || 'N/A'}
                        </div>
                        <div class="tunnel-info">
                            <strong>Exit IP:</strong> ${t.exit_ip || 'N/A'}
                        </div>
                        <div class="tunnel-info">
                            <strong>Status:</strong>
                            <span class="status ${t.status}">${t.status}</span>
                        </div>
                        <button class="btn" onclick="replaceTunnel('${t.country}')">
                            🔄 Replace
                        </button>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Failed to load tunnels:', error);
            }
        }

        async function replaceTunnel(country) {
            if (!confirm(`Replace tunnel for ${country}?`)) return;

            try {
                const response = await fetch(`/api/tunnels/${country}/replace`, {
                    method: 'POST'
                });
                const result = await response.json();
                alert(result.message);
                loadTunnels();
            } catch (error) {
                alert('Failed to replace tunnel');
            }
        }

        // Load tunnels on page load and refresh every 30 seconds
        loadTunnels();
        setInterval(loadTunnels, 30000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    """Serve main page"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/tunnels')
def get_tunnels():
    """Get all tunnels"""
    try:
        db = DatabaseManager("/var/lib/miku/miku.db")
        cursor = db.conn.cursor()

        cursor.execute("""
            SELECT country, port, server_ip, exit_ip, status
            FROM tunnels
            ORDER BY country
        """)

        tunnels = []
        for row in cursor.fetchall():
            tunnels.append({
                'country': row[0],
                'port': row[1],
                'server_ip': row[2],
                'exit_ip': row[3],
                'status': row[4]
            })

        db.close()
        return jsonify(tunnels)

    except Exception as e:
        logger.error(f"Error getting tunnels: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/tunnels/<country>/replace', methods=['POST'])
def replace_tunnel(country):
    """Replace a tunnel"""
    # TODO: Send command to manager
    return jsonify({
        'success': False,
        'message': 'Replace feature requires manager IPC (not yet implemented)'
    }), 501


@app.route('/api/countries')
def get_countries():
    """Get available countries from VPN Gate"""
    try:
        from miku.core.vpngate import VPNGateClient

        client = VPNGateClient()
        countries = client.get_available_countries()

        result = [
            {'code': code, 'name': name, 'count': count}
            for code, name, count in countries
        ]

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error getting countries: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """Get system status"""
    try:
        db = DatabaseManager("/var/lib/miku/miku.db")
        cursor = db.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM tunnels")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tunnels WHERE status = 'running'")
        running = cursor.fetchone()[0]

        db.close()

        return jsonify({
            'total_tunnels': total,
            'running_tunnels': running
        })

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


def run_web_server(host='0.0.0.0', port=8787):
    """Run Flask web server"""
    logger.info(f"Starting web server on {host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_web_server()
