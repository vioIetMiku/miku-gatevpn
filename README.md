# 🎵 Miku-GateVPN

**Multi-exit VPN proxy pool manager powered by VPN Gate**

一键部署的多出口 VPN 代理池管理系统，基于免费的 VPN Gate 节点，使用 Linux Network Namespace 实现完全隔离。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

[English](#english) | [中文](#中文)

---

## 中文

### ✨ 特性

- 🌍 **多国家出口** - 同时运行多个国家的独立隧道（日本、美国、韩国等）
- 🔒 **完全隔离** - 每个 VPN 隧道运行在独立的 Network Namespace 中
- 🔄 **自动故障恢复** - 健康检查 + 自动换节点，无需人工干预
- 🎯 **固定端口** - 每个国家对应固定代理端口，客户端配置不变
- 🚀 **零配置部署** - 一键安装脚本，自动配置所有依赖
- 🖥️ **Web 管理界面** - 实时监控隧道状态，一键换节点
- 📊 **SOCKS5 + HTTP** - 支持两种代理协议
- 💾 **状态持久化** - 重启后自动恢复所有隧道

### 🎯 使用场景

- 需要多国家出口 IP 的爬虫/数据采集
- 跨境电商账号管理（不同国家独立 IP）
- 测试不同地区的网络环境
- 个人/小团队翻墙需求

### 📋 系统要求

- **操作系统**: Ubuntu 20.04+ / Debian 11+ (需要 root 权限)
- **内核版本**: Linux 3.0+ (支持 Network Namespace)
- **Python**: 3.8+
- **依赖**: OpenVPN, iproute2, iptables, socat

### 🚀 快速开始

#### 1. 一键安装

```bash
curl -sSL https://raw.githubusercontent.com/vioIetMiku/miku-gatevpn/main/install.sh | sudo bash
```

安装脚本会自动：
- 检查系统要求
- 安装所有依赖
- 配置 IP 转发和 iptables 规则
- 创建系统目录和服务
- 安装 `miku` 命令行工具

#### 2. 启动服务

```bash
# 启动日本、美国、韩国三个出口
sudo miku start JP US KR

# 或使用 systemd 服务
sudo systemctl start miku
```

#### 3. 查看状态

```bash
miku status
```

输出示例：
```
======================================================================
Miku VPN Gate - Status
======================================================================

JP:
  Port:       7928
  Server IP:  219.100.37.82
  Exit IP:    219.100.37.82
  Status:     running

US:
  Port:       7929
  Server IP:  38.127.169.123
  Exit IP:    38.127.169.123
  Status:     running

KR:
  Port:       7930
  Server IP:  121.162.45.67
  Exit IP:    121.162.45.67
  Status:     running

======================================================================
Total tunnels: 3
======================================================================
```

#### 4. 使用代理

```bash
# 通过日本代理访问
curl -x socks5h://localhost:7928 https://api.ipify.org

# 通过美国代理访问
curl -x socks5h://localhost:7929 https://api.ipify.org

# HTTP 代理方式
curl -x http://localhost:7928 https://httpbin.org/ip
```

#### 5. 访问 Web 界面

浏览器打开：`http://YOUR_VPS_IP:8787`

### 📖 命令行使用

```bash
# 查看可用国家
miku countries

# 启动服务（指定国家）
miku start JP US KR

# 查看状态
miku status

# 测试隧道
miku test JP

# 手动换节点
miku replace JP

# 查看日志
miku logs

# 实时跟踪日志
miku logs -f

# 停止服务
miku stop
```

### 🔧 配置

配置文件位置：`/etc/miku/config.yaml`（未来版本支持）

当前版本通过命令行参数配置：

```bash
# 自定义基础端口
miku start JP US --port 8000
# 日本: 8000, 美国: 8001

# 设置日志级别
miku start JP US --log-level DEBUG
```

### 🌍 支持的国家代码

常用国家代码：

- `JP` - 日本
- `US` - 美国  
- `KR` - 韩国
- `TW` - 台湾
- `UK` - 英国
- `DE` - 德国
- `CA` - 加拿大
- `FR` - 法国
- `TH` - 泰国
- `RU` - 俄罗斯

查看完整列表：`miku countries`

### 🏗️ 架构设计

```
客户端请求
    ↓
SOCKS5/HTTP 代理 (主机 namespace)
    ↓
根据端口选择对应的 Network Namespace
    ↓
NetNS 内的 OpenVPN 隧道
    ↓
VPN Gate 节点
    ↓
目标网站（使用该国家的 IP）
```

**核心技术**：
- **Network Namespace 隔离** - 每个 VPN 独立网络栈
- **SOCKS5 代理** - 支持 TCP 和 UDP
- **健康检查** - 每 30 秒检测出口 IP
- **自动重连** - 失败 3 次后自动换节点
- **状态持久化** - SQLite 存储隧道信息

### 🐛 故障排除

#### 1. 检查服务状态

```bash
systemctl status miku
journalctl -u miku -n 50
```

#### 2. 手动测试 VPN Gate API

```bash
curl -s "https://www.vpngate.net/api/iphone/" | head -20
```

#### 3. 检查 Network Namespace

```bash
ip netns list
# 应该看到: miku_jp, miku_us, miku_kr 等
```

#### 4. 手动进入 namespace 调试

```bash
sudo ip netns exec miku_jp bash
curl https://api.ipify.org
ping -c 3 8.8.8.8
exit
```

#### 5. 查看隧道日志

```bash
cat /var/log/miku/tunnel_jp.log
```

#### 6. 常见问题

**Q: 隧道无法建立连接**
```bash
# 检查 OpenVPN 依赖
which openvpn

# 检查 IP 转发
cat /proc/sys/net/ipv4/ip_forward
# 应该输出 1

# 检查 iptables 规则
sudo iptables -t nat -L -n
```

**Q: 代理连接超时**
```bash
# 测试本地端口
telnet localhost 7928

# 检查进程
ps aux | grep miku
```

**Q: 出口 IP 不正确**
```bash
# 手动检查隧道
sudo ip netns exec miku_jp curl https://api.ipify.org

# 查看健康检查日志
miku logs | grep "Health check"
```

### 📂 项目结构

```
miku-gatevpn/
├── miku/
│   ├── core/
│   │   ├── vpngate.py      # VPN Gate API 客户端
│   │   ├── tunnel.py       # 隧道管理（netns + OpenVPN）
│   │   ├── proxy.py        # SOCKS5/HTTP 代理服务器
│   │   └── health.py       # 健康检查
│   ├── web/
│   │   └── api.py          # Flask Web API
│   ├── manager.py          # 主控调度器
│   └── cli.py              # 命令行入口
├── install.sh              # 一键安装脚本
├── miku.service            # systemd 服务
├── requirements.txt
├── setup.py
└── README.md
```

### ⚠️ 注意事项

1. **仅支持 Linux** - 依赖 Network Namespace 特性
2. **需要 root 权限** - 创建 netns 和配置 iptables
3. **节点质量不稳定** - VPN Gate 节点由志愿者维护，可能随时下线
4. **不保证隐私安全** - 节点流量可能被监控，不要传输敏感信息
5. **遵守当地法律** - 使用 VPN 需遵守所在地区的法律法规

### 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

### 🙏 致谢

- [VPN Gate](https://www.vpngate.net/) - 提供免费 VPN 节点
- [fanout](https://github.com/byJoey/fanout) - 架构设计参考
- [aimili-vpngate](https://github.com/OpenMili/aimili-vpngate) - 功能设计参考

---

## English

### ✨ Features

- 🌍 **Multi-country Exits** - Run multiple isolated tunnels simultaneously
- 🔒 **Complete Isolation** - Each VPN tunnel in separate Network Namespace
- 🔄 **Auto Recovery** - Health checks + automatic node replacement
- 🎯 **Fixed Ports** - Each country has a fixed proxy port
- 🚀 **Zero-config Deploy** - One-click installation script
- 🖥️ **Web Dashboard** - Real-time monitoring and management
- 📊 **SOCKS5 + HTTP** - Support both proxy protocols
- 💾 **State Persistence** - Auto-restore tunnels after restart

### 📋 Requirements

- **OS**: Ubuntu 20.04+ / Debian 11+ (root required)
- **Kernel**: Linux 3.0+ (Network Namespace support)
- **Python**: 3.8+
- **Dependencies**: OpenVPN, iproute2, iptables, socat

### 🚀 Quick Start

#### 1. One-click Install

```bash
curl -sSL https://raw.githubusercontent.com/vioIetMiku/miku-gatevpn/main/install.sh | sudo bash
```

#### 2. Start Service

```bash
sudo miku start JP US KR
```

#### 3. Use Proxies

```bash
# Via Japan proxy
curl -x socks5h://localhost:7928 https://api.ipify.org

# Via USA proxy
curl -x socks5h://localhost:7929 https://api.ipify.org
```

### 📖 CLI Commands

```bash
miku countries          # List available countries
miku start JP US KR     # Start tunnels
miku status             # Show status
miku test JP            # Test tunnel
miku replace JP         # Replace node
miku logs               # View logs
miku logs -f            # Follow logs
miku stop               # Stop service
```

### 🌍 Country Codes

Common codes: `JP` (Japan), `US` (USA), `KR` (Korea), `TW` (Taiwan), `UK` (Britain), `DE` (Germany), `CA` (Canada), `FR` (France), `TH` (Thailand), `RU` (Russia)

Full list: `miku countries`

### 🏗️ Architecture

Each tunnel runs in isolated Network Namespace with dedicated OpenVPN process. Proxy server routes requests to appropriate namespace based on port number.

### ⚠️ Disclaimer

- Linux only (requires Network Namespace)
- Root privileges required
- VPN Gate nodes are volunteer-maintained and may be unstable
- No privacy guarantees - traffic may be monitored
- Comply with local laws regarding VPN usage

### 📄 License

MIT License

---

**Made with ❤️ by VioletMiku**
