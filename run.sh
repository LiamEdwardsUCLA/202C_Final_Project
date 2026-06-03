#!/bin/bash
# Baseline: normal navigation, no attack, no defense.
PROJECT="$(dirname "$(realpath "$0")")"
source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2.launch.py" "Nav2"
_start_navigate

echo "Baseline running — robot navigating normally."
