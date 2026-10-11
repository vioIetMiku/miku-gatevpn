#!/bin/bash
# Miku-GateVPN v2.0 - 智能节点制作工具
# 一键安装脚本

set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# 显示横幅
cat << "EOF"
╔════════════════════════════════════════════════════════╗
║                                                        ║
║        🎵 Miku-GateVPN 智能节点制作工具 v2.0          ║
║                                                        ║
║        为您快速创建高质量翻墙节点                      ║
║                                                        ║
╚════════════════════════════════════════════════════════╝
EOF
echo ""

# 检查 root 权限
if [[ $EUID -ne 0 ]]; then
   log_error "需要 root 权限运行此脚本"
   echo "请使用: sudo bash install.sh"
   exit 1
fi

log_info "开始安装..."

# 检测操作系统
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS=$ID
    log_info "检测到系统: $PRETTY_NAME"
else
    log_error "无法识别操作系统"
    exit 1
fi

# 更新包管理器
log_step "更新包管理器..."
case $OS in
    ubuntu|debian)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        PKG_MANAGER="apt-get"
        ;;
    centos|rhel|fedora)
        yum update -y -q
        PKG_MANAGER="yum"
        ;;
    *)
        log_warn "未测试的操作系统，可能会失败"
        PKG_MANAGER="apt-get"
        ;;
esac

# 安装依赖
log_step "安装系统依赖..."

DEPS="curl wget git python3 python3-pip openvpn iproute2 iptables socat openssl sqlite3"

case $OS in
    ubuntu|debian)
        apt-get install -y $DEPS &> /dev/null
        ;;
    centos|rhel|fedora)
        yum install -y $DEPS &> /dev/null
        ;;
esac

log_info "依赖安装完成"

# 检查 Python 版本
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
log_info "Python 版本: $PYTHON_VERSION"

# 启用 IP 转发
log_step "配置网络..."

if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi
sysctl -w net.ipv4.ip_forward=1 > /dev/null

log_info "IP 转发已启用"

# 配置 iptables NAT
MAIN_IF=$(ip route | grep default | awk '{print $5}' | head -1)
log_info "主网络接口: $MAIN_IF"

# 添加 NAT 规则
if ! iptables -t nat -C POSTROUTING -o $MAIN_IF -j MASQUERADE 2>/dev/null; then
    iptables -t nat -A POSTROUTING -o $MAIN_IF -j MASQUERADE
fi

# 保存规则
if command -v netfilter-persistent &> /dev/null; then
    netfilter-persistent save &> /dev/null
elif command -v iptables-save &> /dev/null; then
    iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
fi

log_info "iptables 规则已配置"

# 创建目录
log_step "创建系统目录..."

mkdir -p /var/lib/miku
mkdir -p /var/log/miku
mkdir -p /etc/miku

log_info "目录创建完成"

# 克隆仓库
log_step "下载 Miku-GateVPN..."

INSTALL_DIR="/opt/miku-gatevpn"

if [[ -d "$INSTALL_DIR" ]]; then
    log_warn "检测到旧版本，正在更新..."
    cd "$INSTALL_DIR"
    git pull &> /dev/null || {
        log_warn "更新失败，重新克隆..."
        cd /opt
        rm -rf miku-gatevpn
        git clone https://github.com/vioIetMiku/miku-gatevpn.git &> /dev/null
    }
else
    cd /opt
    git clone https://github.com/vioIetMiku/miku-gatevpn.git &> /dev/null
fi

cd "$INSTALL_DIR"
log_info "代码下载完成"

# 安装 Python 依赖
log_step "安装 Python 依赖..."

pip3 install -q --upgrade pip
pip3 install -q -r requirements.txt

log_info "Python 依赖安装完成"

# 安装 Miku 包
pip3 install -q -e .

log_info "Miku 包安装完成"

# 创建命令链接
log_step "创建命令链接..."

cat > /usr/local/bin/miku << 'MIKUEOF'
#!/bin/bash
exec python3 -m miku.wizard "$@"
MIKUEOF

chmod +x /usr/local/bin/miku

log_info "命令创建完成"

# 完成安装
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║          安装完成！ 🎉                                     ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

log_info "快速开始:"
echo ""
echo "  1. 运行安装向导:"
echo "     miku"
echo ""
echo "  2. 或者测试检测功能:"
echo "     python3 -m miku.detector.system"
echo "     python3 -m miku.detector.panel"
echo ""
echo "  3. 测试 VPN Gate API:"
echo "     python3 -m miku.outbound.vpngate"
echo ""
echo "  4. 检测节点质量:"
echo "     python3 -m miku.outbound.checker <IP地址>"
echo ""

log_info "文档: https://github.com/vioIetMiku/miku-gatevpn"
echo ""

exit 0
