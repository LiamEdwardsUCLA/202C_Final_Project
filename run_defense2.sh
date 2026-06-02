#!/bin/bash
PROJECT="$(dirname "$(realpath "$0")")"

source /opt/ros/humble/setup.bash
source "$PROJECT/ros_ws/install/setup.bash"
export TURTLEBOT3_MODEL=burger

if [ -z "$GEMINI_API_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY is not set. Export it before running this script."
  exit 1
fi

echo "==> Killing leftover processes..."
killall -q gzserver gzclient ros2 2>/dev/null || true
pkill -f "robot_state_publisher" 2>/dev/null || true
pkill -f "nav2" 2>/dev/null || true
pkill -f "iot_security_demo" 2>/dev/null || true
sleep 3

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

echo "==> Starting Nav2 (LLM defense params: /scan_verified)..."
gnome-terminal --title="Nav2 (LLM defense)" -- bash -c "
  source /opt/ros/humble/setup.bash
  source $PROJECT/ros_ws/install/setup.bash
  export TURTLEBOT3_MODEL=burger
  ros2 launch iot_security_demo nav2_llm.launch.py
  exec bash"

echo "==> Waiting for Nav2..."
until ros2 node list 2>/dev/null | grep -q "amcl"; do
  sleep 2
done
sleep 5
echo "    Nav2 is up."

echo "==> Starting rate filter..."
gnome-terminal --title="Rate Filter" -- bash -c "
  source /opt/ros/humble/setup.bash
  source $PROJECT/ros_ws/install/setup.bash
  ros2 run iot_security_demo rate_filter
  exec bash"

sleep 2

echo "==> Starting LLM monitor..."
gnome-terminal --title="LLM Monitor" -- bash -c "
  source /opt/ros/humble/setup.bash
  source $PROJECT/ros_ws/install/setup.bash
  export GEMINI_API_KEY=$GEMINI_API_KEY
  ros2 run iot_security_demo llm_monitor
  exec bash"

sleep 2

echo "==> Sending navigation goal..."
gnome-terminal --title="Navigate" -- bash -c "
  source /opt/ros/humble/setup.bash
  source $PROJECT/ros_ws/install/setup.bash
  export TURTLEBOT3_MODEL=burger
  ros2 run iot_security_demo navigate
  exec bash"

echo ""
echo "Pipeline: /scan -> rate_filter -> /scan_filtered -> llm_monitor -> /scan_verified -> Nav2"
echo ""
echo "To launch the smart attacker (bypasses rate filter), open a new terminal:"
echo "  source /opt/ros/humble/setup.bash"
echo "  source $PROJECT/ros_ws/install/setup.bash"
echo "  ros2 run iot_security_demo attacker2"
