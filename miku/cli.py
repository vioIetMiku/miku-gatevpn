#!/usr/bin/env python3
"""
主命令行入口
"""
import sys
import click
from miku.web.app import app, socketio


@click.group()
def cli():
    """Miku-GateVPN - 智能节点制作工具"""
    pass


@cli.command()
@click.option('--port', default=8787, help='Web 端口')
@click.option('--host', default='0.0.0.0', help='监听地址')
def web(port, host):
    """启动 Web 管理面板"""
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                                                            ║
║        🎵 Miku-GateVPN Web 管理面板 v2.0                  ║
║                                                            ║
║        访问地址: http://{host}:{port}                     ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝
    """)

    socketio.run(app, host=host, port=port, debug=False)


@cli.command()
def status():
    """查看服务状态"""
    print("Miku-GateVPN 状态:")
    print("  服务: 运行中")
    # TODO: 实现状态检查


if __name__ == '__main__':
    cli()
