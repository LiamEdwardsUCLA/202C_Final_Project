#!/bin/bash
# Attack: publish fake LIDAR wall — robot stops.
#
# ATTACKER options:
#   attacker  — simple clean semicircle, 30 Hz flood  (default)
#   attacker2 — clean semicircle, ~5 Hz (frequency-matched)
#   attacker3 — noisy wall,       ~5 Hz
#   attacker4 — gradual approach, ~5 Hz (hardest)
PROJECT="$(dirname "$(realpath "$0")")"
ATTACKER="${ATTACKER:-attacker}"
source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2.launch.py" "Nav2 (no defense)"
_start_navigate
_start_attacker "$ATTACKER" "Attacker ($ATTACKER)"

echo "Attack running: $ATTACKER — robot should stop."
