#!/bin/bash
# Attack 2: timestamp-spoofed 10 Hz — bypasses rate filter. Robot should stop.
PROJECT="$(dirname "$(realpath "$0")")"
source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2_defense.launch.py" "Nav2 (rate filter)"
_start_rate_filter
_start_navigate
_start_attacker "attacker2" "Attacker 2 (timestamp-spoofed)"

echo ""
echo "Attack 2 running: timestamp-spoofed scans bypass the rate filter."
echo "Rate filter should show zero drops — robot should still be blocked."
