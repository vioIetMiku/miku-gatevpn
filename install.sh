#!/bin/bash
# Miku VPN Gate - One-click installation script
# https://github.com/vioIetMiku/miku-gatevpn

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Banner
cat << "EOF"
    __  __ _ _          __     ______  _   _
   |  \/  (_) | ___   __\ \   / /  _ \| \ | |
   | |\/| | | |/ / | | |\ \ / /| |_) |  \| |
   | |  | | |   <| |_| | \ V / |  __/| |\  |
   |_|  |_|_|_|\_\\__,_|  \_/  |_|   |_| \_|

   VPN Gate Proxy Pool Manager v1.0.0
   https://github.com/vioIetMiku/miku-gatevpn
EOF
echo ""

# 1. Check root privileges
echo_step "Checking privileges..."
if [[ $EUID -ne 0 ]]; then
   echo_error "This script must be run as root"
   echo "Please run: sudo bash install.sh"
   exit 1
fi
echo_info "Running as root ✓"

# 2. Check OS
echo_step "Checking operating system..."
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS=$ID
    echo_info "Detected: $PRETTY_NAME"
else
    echo_error "Cannot determine OS"
    exit 1
fi

if [[ "$OS" != "ubuntu" && "$OS" != "debian" ]]; then
    echo_warn "This script is designed for Ubuntu/Debian"
    echo_warn "Installation may fail on other distributions"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 3. Check kernel version
echo_step "Checking kernel version..."
KERNEL_VERSION=$(uname -r)
echo_info "Kernel version: $KERNEL_VERSION"

KERNEL_MAJOR=$(echo $KERNEL_VERSION | cut -d. -f1)
KERNEL_MINOR=$(echo $KERNEL_VERSION | cut -d. -f2)

if [[ $KERNEL_MAJOR -lt 3 ]]; then
    echo_error "Linux kernel 3.0+ required for network namespace support"
    exit 1
fi
echo_info "Kernel version OK ✓"

# 4. Check Python version
echo_step "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo_error "Python 3 not found. Installing..."
    apt-get update -qq
    apt-get install -y python3 python3-pip
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo_info "Python version: $PYTHON_VERSION"

PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MINOR -lt 8 ]]; then
    echo_error "Python 3.8+ required (found: $PYTHON_VERSION)"
    exit 1
fi
echo_info "Python version OK ✓"

# 5. Install system dependencies
echo_step "Installing system dependencies..."
echo_info "This may take a few minutes..."

export DEBIAN_FRONTEND=noninteractive

apt-get update -qq

apt-get install -y \
    openvpn \
    iproute2 \
    iptables \
    iptables-persistent \
    curl \
    socat \
    python3-pip \
    python3-venv \
    git \
    sqlite3 \
    &> /dev/null

echo_info "Dependencies installed ✓"

# 6. Enable IP forwarding
echo_step "Enabling IP forwarding..."

if ! grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf; then
    echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
fi

sysctl -w net.ipv4.ip_forward=1 > /dev/null
echo_info "IP forwarding enabled ✓"

# 7. Configure iptables
echo_step "Configuring iptables rules..."

# Detect main network interface
MAIN_INTERFACE=$(ip route | grep default | awk '{print $5}' | head -1)
echo_info "Main network interface: $MAIN_INTERFACE"

# Add NAT rules
if ! iptables -t nat -C POSTROUTING -s 10.200.0.0/16 -o $MAIN_INTERFACE -j MASQUERADE 2>/dev/null; then
    iptables -t nat -A POSTROUTING -s 10.200.0.0/16 -o $MAIN_INTERFACE -j MASQUERADE
    echo_info "Added NAT rule for 10.200.0.0/16"
fi

# Allow forwarding from veth interfaces
if ! iptables -C FORWARD -i veth+ -j ACCEPT 2>/dev/null; then
    iptables -A FORWARD -i veth+ -j ACCEPT
    echo_info "Added FORWARD rule for veth interfaces"
fi

# Save rules
netfilter-persistent save &> /dev/null
echo_info "iptables rules configured ✓"

# 8. Create directories
echo_step "Creating system directories..."

mkdir -p /var/lib/miku
mkdir -p /var/log/miku
mkdir -p /etc/miku

chmod 755 /var/lib/miku /var/log/miku /etc/miku
echo_info "Directories created ✓"

# 9. Clean up old installations
echo_step "Cleaning up old installations..."

# Stop service if running
if systemctl is-active --quiet miku 2>/dev/null; then
    systemctl stop miku
    echo_info "Stopped old miku service"
fi

# Remove old namespaces
for ns in $(ip netns list 2>/dev/null | grep "miku_" | awk '{print $1}'); do
    echo_info "Removing old namespace: $ns"
    ip netns del $ns 2>/dev/null || true
done

# Remove old venv
if [[ -d /opt/miku-venv ]]; then
    rm -rf /opt/miku-venv
    echo_info "Removed old virtual environment"
fi

# 10. Clone repository
echo_step "Downloading miku-gatevpn..."

INSTALL_DIR="/opt/miku-gatevpn"

if [[ -d "$INSTALL_DIR" ]]; then
    echo_info "Removing old installation..."
    rm -rf "$INSTALL_DIR"
fi

git clone https://github.com/vioIetMiku/miku-gatevpn.git "$INSTALL_DIR" &> /dev/null

if [[ ! -d "$INSTALL_DIR" ]]; then
    echo_error "Failed to download miku-gatevpn"
    exit 1
fi

cd "$INSTALL_DIR"
echo_info "Downloaded to $INSTALL_DIR ✓"

# 11. Install Python package
echo_step "Installing miku-gatevpn Python package..."

python3 -m venv /opt/miku-venv
source /opt/miku-venv/bin/activate

pip install --upgrade pip setuptools wheel &> /dev/null
pip install -e . &> /dev/null

deactivate
echo_info "Python package installed ✓"

# 12. Create command-line tool
echo_step "Creating miku command..."

cat > /usr/local/bin/miku << 'MIKUEOF'
#!/bin/bash
source /opt/miku-venv/bin/activate
exec python3 -m miku.cli "$@"
MIKUEOF

chmod +x /usr/local/bin/miku
echo_info "Command created: miku ✓"

# 13. Install systemd service
echo_step "Installing systemd service..."

cp miku.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable miku &> /dev/null

echo_info "Systemd service installed ✓"

# 14. Test installation
echo_step "Testing installation..."

if ! command -v miku &> /dev/null; then
    echo_error "miku command not found"
    exit 1
fi

# Test VPN Gate API
if ! miku countries &> /dev/null; then
    echo_warn "VPN Gate API test failed (might be network issue)"
else
    echo_info "VPN Gate API accessible ✓"
fi

# 15. Complete
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}║          Miku VPN Gate Installation Complete! 🎉          ║${NC}"
echo -e "${GREEN}║                                                            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get server IP
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")

echo_info "Quick Start:"
echo ""
echo "  1. Start Miku with countries:"
echo "     miku start JP US KR"
echo ""
echo "  2. Check status:"
echo "     miku status"
echo ""
echo "  3. Test proxy:"
echo "     curl -x socks5h://localhost:7928 https://api.ipify.org"
echo ""
echo "  4. View available countries:"
echo "     miku countries"
echo ""
echo "  5. Access Web UI:"
echo "     http://$SERVER_IP:8787"
echo ""
echo_info "System Service:"
echo ""
echo "  Start:   systemctl start miku"
echo "  Stop:    systemctl stop miku"
echo "  Status:  systemctl status miku"
echo "  Logs:    journalctl -u miku -f"
echo ""
echo_warn "Note: You need to configure which countries to use in /etc/systemd/system/miku.service"
echo_warn "Edit the ExecStart line and then run: systemctl daemon-reload && systemctl restart miku"
echo ""
echo_info "Documentation: https://github.com/vioIetMiku/miku-gatevpn"
echo ""

exit 0
