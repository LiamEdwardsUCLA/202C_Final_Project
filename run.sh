#!/bin/bash
set -e

PROJECT="$(dirname "$(realpath "$0")")"

source /opt/ros/humble/setup.bash
source "$PROJECT/ros_ws/install/setup.bash"
export TURTLEBOT3_MODEL=burger

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
# Wait until the /scan topic is being published (robot is in sim)
until ros2 topic hz /scan --window 3 2>/dev/null | grep -q "average rate"; do
  sleep 2
done
echo "    /scan is live."
sleep 2

echo "==> Starting Nav2..."
gnome-terminal --title="Nav2" -- bash -c "
  source /opt/ros/humble/setup.bash
  source $PROJECT/ros_ws/install/setup.bash
  export TURTLEBOT3_MODEL=burger
  ros2 launch iot_security_demo nav2.launch.py
  exec bash"

echo "==> Waiting for Nav2 (amcl active)..."
until ros2 node list 2>/dev/null | grep -q "amcl"; do
  sleep 2
done
sleep 5
echo "    Nav2 is up."

echo "==> Sending navigation goal..."
gnome-terminal --title="Navigate" -- bash -c "
  source /opt/ros/humble/setup.bash
  source $PROJECT/ros_ws/install/setup.bash
  export TURTLEBOT3_MODEL=burger
  ros2 run iot_security_demo navigate
  exec bash"
