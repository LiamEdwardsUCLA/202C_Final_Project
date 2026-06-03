#!/bin/bash
# Defense 1: rate filter blocks Attack 1. Robot navigates normally.
PROJECT="$(dirname "$(realpath "$0")")"
source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2_defense.launch.py" "Nav2 (rate filter)"
_start_rate_filter
_start_navigate
_start_attacker "attacker" "Attacker 1 (30 Hz flood)"

echo ""
echo "Defense 1 active. Attack 1 (30 Hz) should be blocked by the rate filter."
echo "Robot should navigate normally despite the attacker running."
