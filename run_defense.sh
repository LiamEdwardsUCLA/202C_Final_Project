#!/bin/bash
# Defense: LLM monitor watches /scan, cleans fake data, Nav2 uses /scan_verified.
PROJECT="$(dirname "$(realpath "$0")")"
# ATTACKER options: attacker, attacker2, attacker3, attacker4
ATTACKER="${ATTACKER:-attacker4}"

if [ -z "$GEMINI_API_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY is not set."
  exit 1
fi

source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2_llm.launch.py" "Nav2 (LLM defense)"
_start_llm_monitor
_start_navigate

if [[ "$1" != "--no-attacker" ]]; then
  _start_attacker "$ATTACKER" "Attacker ($ATTACKER)"
  echo "Attacker: $ATTACKER"
else
  echo "No attacker — LLM monitor running in observation mode."
fi

echo ""
echo "Pipeline: /scan -> llm_monitor -> /scan_verified -> Nav2"
echo "Logs: ~/202C_Final_Project/logs/"
