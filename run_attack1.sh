#!/bin/bash
# Attack 1: 30 Hz flood — no defense. Robot should stop.
PROJECT="$(dirname "$(realpath "$0")")"
source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2.launch.py" "Nav2 (no defense)"
_start_navigate
_start_attacker "attacker" "Attacker 1 (30 Hz flood)"

echo ""
echo "Attack 1 running: 30 Hz fake scans on /scan — robot should stop."
