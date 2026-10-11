# Miku-GateVPN 重新设计方案

## 项目定位

**智能节点制作工具** - 为用户快速创建高质量的翻墙节点

### 核心功能

1. **智能环境检测**
   - 检测缺少的工具和依赖
   - 询问用户是否安装
   - 检测已安装的面板（3x-ui, X-UI, V2board 等）

2. **域名管理**
   - 询问是否绑定域名
   - 自动检测域名 DNS 解析
   - 自动获取 SSL 证书（Let's Encrypt）
   - 自动读取现有证书

3. **入口节点配置**
   - 检测现有节点配置
   - 询问是否使用现有节点
   - 或创建新节点，提供多种方案：
     * VLESS + TCP + TLS + Vision
     * VLESS + TCP + Reality
     * VMess + WebSocket + TLS
     * Trojan + TCP + TLS
     * Hysteria2
   - Reality 自动推荐目标域名（10个）
   - TLS 自动读取域名证书

4. **出口节点管理**
   - VPN Gate 节点检测（连通性、速度、延迟）
   - 节点质量评估：
     * 归属地检测
     * 归属商识别
     * IP 纯净度检测（住宅 vs 机房）
     * 流媒体解锁测试
   - 智能节点选择

5. **Web 管理界面**
   - 节点状态监控
   - 一键切换出口
   - 订阅链接生成
   - 流量统计

## 技术架构

```
用户客户端
    ↓
入口节点 (VLESS/VMess/Trojan/Hysteria2)
    ↓ (通过 Xray/Sing-box outbound)
VPN Gate OpenVPN 隧道 (Network Namespace 隔离)
    ↓
目标网站
```

## 安装流程

1. 运行安装脚本
2. 检测环境和依赖
3. 询问是否绑定域名
4. 检测现有面板
5. 配置入口节点
6. 选择出口节点
7. 生成配置和订阅

## 文件结构

```
miku-gatevpn/
├── miku/
│   ├── detector/           # 环境检测
│   │   ├── system.py       # 系统检测
│   │   ├── panel.py        # 面板检测 (3x-ui/X-UI)
│   │   └── domain.py       # 域名检测
│   ├── installer/          # 安装器
│   │   ├── deps.py         # 依赖安装
│   │   ├── ssl.py          # SSL 证书
│   │   └── panel.py        # 面板安装
│   ├── inbound/            # 入口节点
│   │   ├── xray.py         # Xray 配置
│   │   ├── singbox.py      # Sing-box 配置
│   │   └── templates/      # 配置模板
│   ├── outbound/           # 出口节点
│   │   ├── vpngate.py      # VPN Gate API
│   │   ├── checker.py      # 节点检测
│   │   └── tunnel.py       # OpenVPN 隧道
│   ├── web/                # Web 界面
│   │   ├── api.py          # API
│   │   ├── static/         # 前端资源
│   │   └── templates/      # HTML 模板
│   ├── manager.py          # 主控制器
│   └── cli.py              # 命令行
├── install.sh              # 一键安装
└── README.md
```

## 关键功能实现

### 1. 面板检测

```python
def detect_panels():
    panels = []
    
    # 检测 3x-ui
    if os.path.exists('/usr/local/x-ui'):
        panels.append({
            'name': '3x-ui',
            'path': '/usr/local/x-ui',
            'port': detect_3xui_port(),
            'version': get_3xui_version()
        })
    
    # 检测 X-UI
    if os.path.exists('/usr/local/x-ui'):
        panels.append({
            'name': 'X-UI',
            'path': '/usr/local/x-ui'
        })
    
    return panels
```

### 2. 节点配置生成

```python
def generate_vless_reality(domain, reality_target):
    config = {
        "protocol": "vless",
        "settings": {
            "clients": [{
                "id": str(uuid.uuid4()),
                "flow": "xtls-rprx-vision"
            }]
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "dest": reality_target,
                "serverNames": [reality_target],
                "privateKey": generate_reality_keypair()[0],
                "shortIds": [generate_short_id()]
            }
        }
    }
    return config
```

### 3. VPN Gate 节点检测

```python
async def check_node_quality(node_ip):
    results = {
        'connectivity': await check_connectivity(node_ip),
        'speed': await test_speed(node_ip),
        'location': await get_location(node_ip),
        'isp': await get_isp_info(node_ip),
        'purity': await check_residential(node_ip),
        'streaming': await test_streaming(node_ip)
    }
    return results
```

## 用户交互流程

```
$ curl -sSL https://raw.githubusercontent.com/vioIetMiku/miku-gatevpn/main/install.sh | bash

> 检测系统环境...
> 缺少以下工具：curl, socat, openvpn
> 是否安装? [Y/n]: y
> 正在安装依赖...

> 是否绑定域名? [y/N]: y
> 请输入域名: miku.example.com
> 检测 DNS 解析... ✓
> 检测 SSL 证书... 未找到
> 是否自动申请 Let's Encrypt 证书? [Y/n]: y

> 检测到已安装的面板:
>   1. 3x-ui (端口 2053)
> 是否使用现有面板? [Y/n]: y

> 检测到现有节点:
>   1. VLESS + TCP (端口 443)
>   2. VMess + WS (端口 80)
> 是否使用这些节点作为入口? [Y/n]: y
> 选择节点 [1-2]: 1

> 正在获取 VPN Gate 节点列表...
> 找到 156 个可用节点

> 请选择出口国家:
>   1. 日本 (45 个节点)
>   2. 美国 (32 个节点)
>   3. 韩国 (28 个节点)
> 选择 [1-3]: 1

> 正在检测节点质量...
> 推荐节点:
>   1. 219.100.37.82 (东京, NTT, 住宅IP, 8ms, 28Mbps) ⭐⭐⭐⭐⭐
>   2. 133.242.xxx.xxx (大阪, SoftBank, 住宅IP, 12ms, 22Mbps) ⭐⭐⭐⭐
> 选择节点 [1-2]: 1

> 正在配置...
> ✓ 创建 OpenVPN 隧道
> ✓ 配置 Xray outbound
> ✓ 重启服务

> 安装完成!
> 
> Web 管理界面: https://miku.example.com:8787
> 订阅链接: https://miku.example.com:8787/sub/xxxxx
```

## 下一步行动

1. 重构现有代码
2. 实现环境检测模块
3. 实现面板集成
4. 实现节点配置生成
5. 实现 VPN Gate 质量检测
6. 实现 Web 管理界面
7. 完善安装脚本

预计工作量：3-5 天
