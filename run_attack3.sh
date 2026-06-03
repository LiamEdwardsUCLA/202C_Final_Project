#!/bin/bash
# Attack 3: noisy timestamp-spoofed wall — bypasses rate filter, harder for LLM.
PROJECT="$(dirname "$(realpath "$0")")"
source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2_defense.launch.py" "Nav2 (rate filter)"
_start_rate_filter
_start_navigate
_start_attacker "attacker3" "Attacker 3 (noisy wall)"

echo ""
echo "Attack 3 running: noisy wall with dropouts and arc jitter bypasses rate filter."
echo "Rate filter should show zero drops — robot should still be blocked."
