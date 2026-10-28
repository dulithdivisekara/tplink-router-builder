#!/usr/bin/env bash
# ==============================================================================
# Linux Client-Side Network Optimizer for 4G LTE Connections (Hutch / TP-Link)
# ==============================================================================
# Usage:
#   sudo ./optimize-network.sh enable    # Apply LTE-optimized kernel & MTU parameters
#   sudo ./optimize-network.sh disable   # Instantly revert back to default Linux settings
#   ./optimize-network.sh status         # Check current network parameters & latency
# ==============================================================================

BACKUP_FILE="/tmp/tplink_netopt_backup.env"

# Detect primary Wi-Fi interface
get_wifi_interface() {
    local iface
    iface=$(ip route show default 2>/dev/null | awk '{print $5}' | head -n 1)
    if [ -z "$iface" ]; then
        iface=$(ip -o link show | awk -F': ' '{print $2}' | grep -E '^wl' | head -n 1)
    fi
    echo "${iface:-wlo1}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "\033[91m[Error] This operation requires root privileges. Please run with sudo:\033[0m"
        echo "  sudo $0 $1"
        exit 1
    fi
}

do_status() {
    local iface
    iface=$(get_wifi_interface)
    local cc qdisc mtu
    cc=$(sysctl -n net.ipv4.tcp_congestion_control 2>/dev/null)
    qdisc=$(sysctl -n net.core.default_qdisc 2>/dev/null)
    mtu=$(ip link show dev "$iface" 2>/dev/null | grep -o 'mtu [0-9]*' | awk '{print $2}')

    echo ""
    echo "================================================================="
    echo "            CURRENT LINUX NETWORK TUNING STATUS                  "
    echo "================================================================="
    echo -e "Primary Interface         : \033[1m$iface\033[0m"
    echo -e "TCP Congestion Control    : \033[1m$cc\033[0m $([ "$cc" == "bbr" ] && echo -e "\033[92m(BBR - Optimized for LTE)\033[0m" || echo -e "\033[93m(CUBIC - Default)\033[0m")"
    echo -e "Default Queuing Discipline: \033[1m$qdisc\033[0m"
    echo -e "Interface MTU             : \033[1m${mtu:-Unknown}\033[0m $([ "$mtu" == "1420" ] && echo -e "\033[92m(1420 - Clamped for LTE GTP)\033[0m" || echo -e "\033[93m(1500 - Standard)\033[0m")"
    echo -e "Optimization State        : $([ -f "$BACKUP_FILE" ] && echo -e "\033[92mACTIVE (Backup saved in $BACKUP_FILE)\033[0m" || echo -e "\033[90mINACTIVE / DEFAULT\033[0m")"
    echo "-----------------------------------------------------------------"
    echo "Latency Benchmarks:"
    echo -n "  Google DNS (8.8.8.8)    : "
    ping -c 2 -W 2 8.8.8.8 2>/dev/null | tail -1 | awk -F '/' '{print $5 " ms (avg)"}' || echo "Timed out"
    echo -n "  Cloudflare (1.1.1.1)    : "
    ping -c 2 -W 2 1.1.1.1 2>/dev/null | tail -1 | awk -F '/' '{print $5 " ms (avg)"}' || echo "Timed out"
    echo -n "  Router Gateway          : "
    ping -c 2 -W 1 192.168.1.1 2>/dev/null | tail -1 | awk -F '/' '{print $5 " ms (avg)"}' || echo "Timed out"
    echo "================================================================="
    echo ""
}

do_enable() {
    check_root "enable"
    local iface
    iface=$(get_wifi_interface)

    local gw
    gw=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n 1)
    if [ -n "$gw" ] && [[ "$gw" == 172.16.* || "$gw" == 10.* ]]; then
        echo -e "\033[93m[Network Guard Notice] Your active gateway is $gw (likely Campus / Enterprise Wi-Fi).\033[0m"
        echo -e "Applying MTU 1420 is intended for 4G cellular links. Continuing..."
    fi

    echo -e "\033[1mEnabling 4G LTE Network Optimizations...\033[0m"

    # 1. Back up original settings if not already backed up
    if [ ! -f "$BACKUP_FILE" ]; then
        local orig_cc orig_qdisc orig_mtu orig_idle orig_rmem orig_wmem
        orig_cc=$(sysctl -n net.ipv4.tcp_congestion_control)
        orig_qdisc=$(sysctl -n net.core.default_qdisc)
        orig_mtu=$(ip link show dev "$iface" | grep -o 'mtu [0-9]*' | awk '{print $2}')
        orig_idle=$(sysctl -n net.ipv4.tcp_slow_start_after_idle)
        orig_rmem=$(sysctl -n net.core.rmem_max)
        orig_wmem=$(sysctl -n net.core.wmem_max)

        cat <<EOF > "$BACKUP_FILE"
ORIG_IFACE="$iface"
ORIG_CC="$orig_cc"
ORIG_QDISC="$orig_qdisc"
ORIG_MTU="$orig_mtu"
ORIG_IDLE="$orig_idle"
ORIG_RMEM="$orig_rmem"
ORIG_WMEM="$orig_wmem"
EOF
        echo -e "  Saved original baseline settings to \033[94m$BACKUP_FILE\033[0m."
    fi

    # 2. Load and enable TCP BBR
    modprobe tcp_bbr 2>/dev/null || true
    if grep -q bbr /proc/sys/net/ipv4/tcp_available_congestion_control 2>/dev/null; then
        sysctl -w net.ipv4.tcp_congestion_control=bbr >/dev/null
        echo -e "  \033[92m[✓]\033[0m TCP Congestion Control set to \033[1mBBR\033[0m (handles cellular jitter & packet drops)"
    else
        echo -e "  \033[93m[!]\033[0m BBR module not available; keeping existing congestion control"
    fi

    # 3. Configure Fair Queuing (fq / fq_codel) to eliminate bufferbloat
    sysctl -w net.core.default_qdisc=fq >/dev/null 2>&1 || sysctl -w net.core.default_qdisc=fq_codel >/dev/null
    echo -e "  \033[92m[✓]\033[0m Default Queueing Discipline set to \033[1mfq\033[0m (bufferbloat prevention)"

    # 4. Disable slow-start restart after idle (keeps TCP pipe warm across quiet periods)
    sysctl -w net.ipv4.tcp_slow_start_after_idle=0 >/dev/null
    sysctl -w net.ipv4.tcp_window_scaling=1 >/dev/null
    echo -e "  \033[92m[✓]\033[0m Disabled TCP slow-start after idle (eliminates pause lag without flood pinging)"

    # 5. Tune TCP socket buffer limits
    sysctl -w net.core.rmem_max=16777216 >/dev/null
    sysctl -w net.core.wmem_max=16777216 >/dev/null
    echo -e "  \033[92m[✓]\033[0m Enlarged TCP buffer limits (16 MB window capability)"

    # 6. Clamp MTU to 1420 on wireless interface to prevent LTE GTP tunnel fragmentation
    if ip link set dev "$iface" mtu 1420 2>/dev/null; then
        echo -e "  \033[92m[✓]\033[0m Interface \033[1m$iface\033[0m MTU clamped to \033[1m1420\033[0m (eliminates 4G packet fragmentation)"
    else
        echo -e "  \033[93m[!]\033[0m Could not set MTU on interface $iface"
    fi

    echo ""
    echo -e "\033[92mOptimization applied successfully!\033[0m"
    echo "To revert when switching to campus Wi-Fi, run:"
    echo "  sudo $0 disable"
}

do_disable() {
    check_root "disable"
    local iface
    iface=$(get_wifi_interface)

    echo -e "\033[1mReverting Network Optimizations to Defaults...\033[0m"

    if [ -f "$BACKUP_FILE" ]; then
        # Load saved backup
        # shellcheck disable=SC1090
        source "$BACKUP_FILE"
        sysctl -w "net.ipv4.tcp_congestion_control=${ORIG_CC:-cubic}" >/dev/null 2>&1
        sysctl -w "net.core.default_qdisc=${ORIG_QDISC:-fq_codel}" >/dev/null 2>&1
        sysctl -w "net.ipv4.tcp_slow_start_after_idle=${ORIG_IDLE:-1}" >/dev/null 2>&1
        sysctl -w "net.core.rmem_max=${ORIG_RMEM:-212992}" >/dev/null 2>&1
        sysctl -w "net.core.wmem_max=${ORIG_WMEM:-212992}" >/dev/null 2>&1
        ip link set dev "${ORIG_IFACE:-$iface}" mtu "${ORIG_MTU:-1500}" 2>/dev/null || true
        rm -f "$BACKUP_FILE"
        echo -e "  \033[92m[✓]\033[0m Restored parameters from backup file."
    else
        # Standard Ubuntu defaults fallback
        sysctl -w net.ipv4.tcp_congestion_control=cubic >/dev/null 2>&1
        sysctl -w net.core.default_qdisc=fq_codel >/dev/null 2>&1
        sysctl -w net.ipv4.tcp_slow_start_after_idle=1 >/dev/null 2>&1
        ip link set dev "$iface" mtu 1500 2>/dev/null || true
        echo -e "  \033[92m[✓]\033[0m Restored standard defaults (CUBIC, MTU 1500, fq_codel)."
    fi

    echo ""
    echo -e "\033[92mRevert complete! Network is clean and ready for Campus / Public Wi-Fi.\033[0m"
}

case "$1" in
    enable)
        do_enable
        ;;
    disable|revert)
        do_disable
        ;;
    status)
        do_status
        ;;
    *)
        echo "Usage: $0 {enable|disable|status}"
        echo ""
        echo "Commands:"
        echo "  enable  : Optimize Linux kernel (BBR) & MTU (1420) for Hutch 4G"
        echo "  disable : Revert back to stock Linux settings (for SLIIT campus Wi-Fi)"
        echo "  status  : View current settings and latency"
        exit 1
        ;;
esac
