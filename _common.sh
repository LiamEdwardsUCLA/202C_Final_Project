#!/bin/bash
# Shared startup logic — sourced by scenario scripts, not run directly.
# Expects PROJECT to already be set.

source /opt/ros/humble/setup.bash
source "$PROJECT/ros_ws/install/setup.bash"
export TURTLEBOT3_MODEL=burger

_kill_all() {
  echo "==> Killing leftover processes..."
  killall -q gzserver gzclient ros2 2>/dev/null || true
  pkill -f "robot_state_publisher" 2>/dev/null || true
  pkill -f "nav2" 2>/dev/null || true
  pkill -f "iot_security_demo" 2>/dev/null || true
  sleep 3
}

_start_gazebo() {
  echo "==> Starting Gazebo..."
  gnome-terminal --title="Gazebo" -- bash -c "
    source /opt/ros/humble/setup.bash
    source $PROJECT/ros_ws/install/setup.bash
    export TURTLEBOT3_MODEL=burger
    ros2 launch iot_security_demo gazebo.launch.py
    exec bash"

  echo "==> Waiting for Gazebo + robot spawn..."
  until ros2 topic hz /scan --window 3 2>/dev/null | grep -q "average rate"; do
    sleep 2
  done
  echo "    /scan is live."
  sleep 2
}

_start_nav2() {
  local launch="${1:-nav2.launch.py}"
  local title="${2:-Nav2}"
  echo "==> Starting $title..."
  gnome-terminal --title="$title" -- bash -c "
    source /opt/ros/humble/setup.bash
    source $PROJECT/ros_ws/install/setup.bash
    export TURTLEBOT3_MODEL=burger
    ros2 launch iot_security_demo $launch
    exec bash"

  echo "==> Waiting for Nav2 (amcl)..."
  until ros2 node list 2>/dev/null | grep -q "amcl"; do
    sleep 2
  done
  sleep 5
  echo "    Nav2 is up."
}

_start_rate_filter() {
  echo "==> Starting rate filter..."
  gnome-terminal --title="Rate Filter" -- bash -c "
    source /opt/ros/humble/setup.bash
    source $PROJECT/ros_ws/install/setup.bash
    ros2 run iot_security_demo rate_filter
    exec bash"
  sleep 2
}

_start_llm_monitor() {
  echo "==> Starting LLM monitor..."
  gnome-terminal --title="LLM Monitor" -- bash -c "
    source /opt/ros/humble/setup.bash
    source $PROJECT/ros_ws/install/setup.bash
    export GEMINI_API_KEY=$GEMINI_API_KEY
    ros2 run iot_security_demo llm_monitor
    exec bash"
  sleep 2
}

_start_navigate() {
  echo "==> Sending navigation goal..."
  gnome-terminal --title="Navigate" -- bash -c "
    source /opt/ros/humble/setup.bash
    source $PROJECT/ros_ws/install/setup.bash
    export TURTLEBOT3_MODEL=burger
    ros2 run iot_security_demo navigate
    exec bash"
}

_start_attacker() {
  local node="$1"
  local title="$2"
  local delay="${3:-8}"
  echo "==> Waiting ${delay}s for robot to start moving..."
  sleep "$delay"
  echo "==> Launching $title..."
  gnome-terminal --title="$title" -- bash -c "
    source /opt/ros/humble/setup.bash
    source $PROJECT/ros_ws/install/setup.bash
    ros2 run iot_security_demo $node
    exec bash"
}
