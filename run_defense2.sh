#!/bin/bash
# Defense 2: LLM monitor catches Attacks 2 & 3. Robot navigates normally.
# Usage: ATTACKER=attacker2|attacker3 ./run_defense2.sh  (default: attacker3)
PROJECT="$(dirname "$(realpath "$0")")"

if [ -z "$GEMINI_API_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY is not set. Export it before running this script."
  exit 1
fi

ATTACKER="${ATTACKER:-attacker3}"

source "$PROJECT/_common.sh"

_kill_all
_start_gazebo
_start_nav2 "nav2_llm.launch.py" "Nav2 (LLM defense)"
_start_rate_filter
_start_llm_monitor
_start_navigate
_start_attacker "$ATTACKER" "Attacker ($ATTACKER)"

echo ""
echo "Defense 2 active. Pipeline: /scan -> rate_filter -> /scan_filtered -> llm_monitor -> /scan_verified -> Nav2"
echo "Attacker: $ATTACKER"
echo "Gemini will query every 10s. Check the LLM Monitor terminal for detections."
echo "Conversation logs: ~/202C_Final_Project/logs/"
