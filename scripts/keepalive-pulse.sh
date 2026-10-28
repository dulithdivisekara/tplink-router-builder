#!/usr/bin/env bash
# ==============================================================================
# Lightweight Cellular RRC_CONNECTED Keepalive Pulse
# ==============================================================================
# Purpose:
#   Maintains cellular modem in RRC_CONNECTED state by sending a tiny 28-byte
#   ICMP heartbeat every 6 seconds to a nearby DNS resolver (8.8.8.8).
#   Eliminates the 50-100ms RRC promotion delay without inducing bufferbloat
#   or consuming noticeable data (~0.5 KB per minute).
#
# Usage:
#   ./keepalive-pulse.sh start    # Start pulse in background
#   ./keepalive-pulse.sh stop     # Stop pulse
#   ./keepalive-pulse.sh run      # Run in foreground with live timing
#   ./keepalive-pulse.sh status   # Check if running
# ==============================================================================

PID_FILE="/tmp/tplink_keepalive.pid"
LOG_FILE="/tmp/tplink_keepalive.log"
TARGET="8.8.8.8"
INTERVAL=6

do_run() {
    echo -e "\033[92mStarting keepalive pulse to $TARGET (interval: ${INTERVAL}s)...\033[0m"
    echo "Press Ctrl+C to stop."
    while true; do
        ts=$(date +'%H:%M:%S')
        rtt=$(ping -c 1 -s 0 -W 2 "$TARGET" 2>/dev/null | grep 'time=' | awk -F'time=' '{print $2}')
        if [ -n "$rtt" ]; then
            echo "[$ts] Keepalive pulse -> $TARGET: $rtt (Radio RRC_CONNECTED maintained)"
        else
            echo "[$ts] Keepalive pulse -> $TARGET: No reply"
        fi
        sleep "$INTERVAL"
    done
}

do_start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "\033[93mKeepalive pulse is already running (PID: $(cat "$PID_FILE")).\033[0m"
        return
    fi

    nohup bash -c "while true; do ping -c 1 -s 0 -W 2 '$TARGET' >/dev/null 2>&1; sleep '$INTERVAL'; done" >/dev/null 2>&1 &
    echo $! > "$PID_FILE"
    echo -e "\033[92mKeepalive pulse started in background (PID: $(cat "$PID_FILE")).\033[0m"
    echo "LTE radio state will be kept warm. To stop, run:"
    echo "  $0 stop"
}

do_stop() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo -e "\033[92mKeepalive pulse (PID: $pid) stopped.\033[0m"
        else
            echo "Keepalive process was not running."
        fi
        rm -f "$PID_FILE"
    else
        echo "No active keepalive PID file found."
    fi
}

do_status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "Keepalive pulse status: \033[92mRUNNING (PID: $(cat "$PID_FILE"))\033[0m"
    else
        echo -e "Keepalive pulse status: \033[90mSTOPPED\033[0m"
    fi
}

case "$1" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    run)
        do_run
        ;;
    status)
        do_status
        ;;
    *)
        echo "Usage: $0 {start|stop|run|status}"
        exit 1
        ;;
esac
