# 🎵 Miku-GateVPN v2.0

**智能节点制作工具 - 快速创建高质量翻墙节点**

一键部署的节点制作工具，自动检测环境、集成现有面板（3x-ui/X-UI），智能选择 VPN Gate 优质节点，支持多种协议配置。

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## ✨ 核心功能

### 🔍 智能环境检测
- ✅ 自动检测操作系统和缺失依赖
- ✅ 识别已安装的面板（3x-ui, X-UI, Xray, Sing-box）
- ✅ 读取现有节点配置
- ✅ 智能推荐配置方案

### 🌐 域名和证书管理
- ✅ DNS 解析自动检测
- ✅ 自动发现现有 SSL 证书（acme.sh, certbot, 3x-ui）
- ✅ 一键申请 Let's Encrypt 证书
- ✅ TLS 配置自动填充

### 📥 多协议入口节点
- ✅ **VLESS + TCP + TLS + Vision** (推荐)
- ✅ **VLESS + TCP + Reality** (无需域名)
- ✅ VMess + WebSocket + TLS
- ✅ Trojan + TCP + TLS
- ✅ Hysteria2
- ✅ Reality 自动推荐目标域名（10个）
- ✅ 自动读取域名证书文件

### 📤 智能出口节点选择
- ✅ VPN Gate 节点连通性检测
- ✅ IP 归属地和 ISP 识别
- ✅ **IP 纯净度评估**（住宅 vs 机房）
- ✅ 延迟和速度测试
- ✅ 综合评分系统（⭐-⭐⭐⭐⭐⭐）
- ✅ 流媒体解锁测试

### 🎯 交互式安装向导
- ✅ 友好的问答式流程
- ✅ 自动安装缺失工具
- ✅ 一键完成全部配置
- ✅ 实时显示进度

---

## 🚀 快速开始

### 一键安装

```bash
curl -sSL https://raw.githubusercontent.com/vioIetMiku/miku-gatevpn/main/install.sh | sudo bash
```

安装完成后，**打开浏览器访问 Web 管理面板**：

```
http://您的服务器IP:8787
```

**所有配置都在 Web 界面完成，无需 SSH 操作！**

### 安装流程演示

```
╔════════════════════════════════════════════════════════╗
║        🎵 Miku-GateVPN 智能节点制作工具 v2.0          ║
╚════════════════════════════════════════════════════════╝

📋 正在检查系统环境...
✅ Root 权限
✅ 网络正常 (公网IP: 1.2.3.4)
✅ Ubuntu 22.04
✅ 所有依赖已安装

🌐 域名配置
是否绑定域名? [y/N]: y
请输入域名: miku.example.com
✅ DNS 解析成功: 1.2.3.4
✅ 找到现有 SSL 证书

🔍 正在检测已安装的面板...
检测到以下面板:
  1. 3x-ui
     Web 端口: 2053
     入站节点: 2 个

是否使用现有面板? [Y/n]: y

📥 配置入口节点
检测到现有入站节点:
  1. VLESS Reality
     协议: vless
     端口: 443

是否使用这些节点作为入口? [Y/n]: y

📤 选择出口节点
正在从 VPN Gate 获取节点列表...
找到 156 个可用节点

请选择出口国家:
  1. 日本 (45 个节点)
  2. 美国 (32 个节点)
  3. 韩国 (28 个节点)

选择 [1-3]: 1

正在检测节点质量...
推荐节点:
  1. 219.100.37.82 (东京, NTT, 🏠住宅IP, 8ms, 28Mbps) ⭐⭐⭐⭐⭐
  2. 133.242.xxx.xxx (大阪, SoftBank, 🏠住宅IP, 12ms, 22Mbps) ⭐⭐⭐⭐

选择节点 [1-2]: 1

✅ 安装完成!

Web 管理界面: https://miku.example.com:8787
订阅链接: https://miku.example.com:8787/sub/xxxxx
```

---

## 📖 功能模块

### 1. 系统检测 (`detector/system.py`)

```bash
python3 -m miku.detector.system
```

检测项目：
- 操作系统信息
- Root 权限
- 网络连接和公网 IP
- 依赖工具（curl, openvpn, socat 等）
- 已安装的面板

### 2. 面板检测 (`detector/panel.py`)

```bash
python3 -m miku.detector.panel
```

支持的面板：
- **3x-ui** - 完整集成，读取入站配置
- **X-UI** - 基础支持
- **Xray 原生** - 直接读取 config.json
- **Sing-box** - 配置文件解析

### 3. VPN Gate API (`outbound/vpngate.py`)

```bash
# 查看可用国家
python3 -m miku.outbound.vpngate

# 查看日本最佳节点
python3 -m miku.outbound.vpngate JP
```

功能：
- 从 VPN Gate 获取实时节点列表
- 解析 OpenVPN 配置
- 按国家筛选
- 质量评分排序
- 住宅 IP 识别

### 4. 节点质量检测 (`outbound/checker.py`)

```bash
# 检测单个 IP
python3 -m miku.outbound.checker 219.100.37.82

# 批量检测
python3 -m miku.outbound.checker 1.2.3.4 5.6.7.8 9.10.11.12
```

检测维度：
- ✅ 连通性和延迟
- ✅ 地理位置（国家/地区/城市）
- ✅ ISP 和 AS 信息
- ✅ **IP 类型**（住宅/移动/机房/代理）
- ✅ **纯净度评分**（0-100）
- ✅ 综合评级（⭐-⭐⭐⭐⭐⭐）

输出示例：
```
IP: 219.100.37.82
连通性: ✓
延迟: 8ms
类型: residential
纯净度: 95/100
综合评分: 94/100 ⭐⭐⭐⭐⭐

详细信息:
  国家: Japan (JP)
  地区: Tokyo, Tokyo
  ISP: NTT Communications
  AS: AS4713
```

### 5. Xray 配置生成 (`inbound/xray.py`)

支持的协议：
- VLESS + TCP + TLS + Vision
- VLESS + TCP + Reality
- VMess + WebSocket + TLS
- Trojan + TCP + TLS

Reality 推荐域名：
- www.microsoft.com
- www.apple.com
- www.cloudflare.com
- www.amazon.com
- （更多...）

### 6. OpenVPN 隧道管理 (`outbound/tunnel.py`)

基于 Network Namespace 完全隔离：
- 每个国家独立 netns
- OpenVPN 在 netns 中运行
- 自动检测连接状态
- 获取真实出口 IP

---

## 🏗️ 项目架构

```
用户客户端
    ↓
入口节点 (VLESS/VMess/Trojan/Hysteria2)
    ↓ (Xray/Sing-box outbound)
SOCKS5 代理 (母机)
    ↓ (setns 切换到 netns)
OpenVPN 隧道 (Network Namespace)
    ↓
VPN Gate 节点
    ↓
目标网站
```

### 技术栈

- **Python 3.8+** - 主要开发语言
- **Network Namespace** - VPN 隔离
- **OpenVPN** - VPN 协议
- **Xray/Sing-box** - 入口节点
- **VPN Gate API** - 免费节点源

---

## 📂 项目结构

```
miku-gatevpn/
├── miku/
│   ├── detector/              # 检测模块
│   │   ├── system.py          # 系统环境检测
│   │   ├── domain.py          # 域名和证书管理
│   │   └── panel.py           # 面板检测
│   ├── inbound/               # 入口节点
│   │   └── xray.py            # Xray 配置生成
│   ├── outbound/              # 出口节点
│   │   ├── vpngate.py         # VPN Gate API
│   │   ├── checker.py         # 节点质量检测
│   │   └── tunnel.py          # OpenVPN 隧道
│   └── wizard.py              # 交互式向导
├── install.sh                 # 一键安装脚本
├── requirements.txt
├── setup.py
└── README.md
```

---

## 🎯 使用场景

1. **个人翻墙** - 快速搭建自己的节点
2. **节点分享** - 为朋友提供高质量节点
3. **测试环境** - 不同国家 IP 测试
4. **数据采集** - 多国家出口爬虫
5. **跨境电商** - 账号管理专用 IP

---

## 🔧 高级用法

### 手动测试各模块

```bash
# 1. 测试系统检测
python3 -m miku.detector.system

# 2. 测试面板检测
python3 -m miku.detector.panel

# 3. 测试域名检测
python3 -m miku.detector.domain miku.example.com

# 4. 获取 VPN Gate 节点
python3 -m miku.outbound.vpngate JP

# 5. 检测节点质量
python3 -m miku.outbound.checker 219.100.37.82

# 6. 生成 Xray 配置
python3 -m miku.inbound.xray
```

### 集成到现有面板

如果你已经有 3x-ui 或 Xray：
1. 运行向导会自动检测
2. 选择使用现有入站节点
3. 只需配置出口即可

---

## ⚠️ 注意事项

1. **仅支持 Linux** - 依赖 Network Namespace
2. **需要 root 权限** - 创建 netns 和配置 iptables
3. **节点质量波动** - VPN Gate 节点由志愿者维护
4. **隐私安全** - 节点流量可能被监控，不要传输敏感信息
5. **遵守法律** - 使用需遵守所在地区法律法规

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

### 开发计划

- [ ] Web 管理界面
- [ ] 订阅链接生成
- [ ] 自动健康检查和切换
- [ ] 流量统计
- [ ] Docker 支持
- [ ] Sing-box 配置生成
- [ ] 更多协议支持（Shadowsocks, Hysteria2）

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

## 🙏 致谢

- [VPN Gate](https://www.vpngate.net/) - 免费 VPN 节点
- [3x-ui](https://github.com/MHSanaei/3x-ui) - 优秀的 Xray 面板
- [Xray-core](https://github.com/XTLS/Xray-core) - 强大的代理工具
- [fanout](https://github.com/byJoey/fanout) - Network Namespace 架构参考

---

**Made with ❤️ by VioletMiku**

_智能节点制作工具，让翻墙变得简单_
