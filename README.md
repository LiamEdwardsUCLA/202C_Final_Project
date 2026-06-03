# LLM-Assisted LIDAR Spoofing Detection in ROS2

ECE 202C — Final Project

Demonstrates LIDAR spoofing attacks on a simulated autonomous robot and an LLM-based defense using Gemini.

---

## Prerequisites

- ROS2 Humble
- TurtleBot3 simulation packages:
  ```bash
  sudo apt install ros-humble-turtlebot3 ros-humble-turtlebot3-gazebo ros-humble-turtlebot3-simulations
  ```
- Google GenAI Python SDK:
  ```bash
  pip install google-genai
  ```
- A Gemini API key (for the defense)

---

## Build

```bash
cd ~/202C_Final_Project/ros_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

---

## Running

### Baseline — robot navigates normally

```bash
./run.sh
```

TurtleBot3 navigates from (-2, -0.5) to (2, 0) in the turtlebot3_world map using Nav2 + AMCL.

---

### Attack — robot is blocked

```bash
./run_attack.sh                         # simple 30 Hz flood (default)
ATTACKER=attacker2 ./run_attack.sh      # frequency-matched clean wall
ATTACKER=attacker3 ./run_attack.sh      # frequency-matched noisy wall
ATTACKER=attacker4 ./run_attack.sh      # gradual approach (hardest)
```

An attacker node publishes fake LIDAR scans on `/scan`. Nav2 has no way to verify the source — the robot sees the fake wall and stops.

| Attacker | Rate | Description |
|---|---|---|
| `attacker` | 30 Hz | Simple clean semicircle — flood attack |
| `attacker2` | ~5 Hz | Clean semicircle, frequency-matched |
| `attacker3` | ~5 Hz | Noisy wall with dropouts and arc jitter |
| `attacker4` | ~5 Hz | ±45° wall rotating 15°/scan — always intercepts the planned path |

---

### Defense — LLM monitor detects and cleans the attack

```bash
export GEMINI_API_KEY=your_key_here
./run_defense.sh                        # gradual approach attacker (default)
ATTACKER=attacker3 ./run_defense.sh     # noisy wall
ATTACKER=attacker  ./run_defense.sh     # simple flood
```

The LLM monitor sits between `/scan` and Nav2:

```
/scan  →  llm_monitor  →  /scan_verified  →  Nav2
```

Every 10 seconds it sends Gemini a snapshot of recent scan data (min range per 60° sector) and robot odometry. When an attack is detected, suspicious rays are restored to their historical median rather than zeroed — real obstacles are preserved, fake ones are removed. The robot resumes navigating.

Conversation logs are saved to `~/202C_Final_Project/logs/`.

---

## Project Structure

```
ros_ws/src/iot_security_demo/
  iot_security_demo/
    attacker.py        # 30 Hz flood
    attacker2.py       # ~5 Hz clean wall
    attacker3.py       # ~5 Hz noisy wall
    attacker4.py       # ~5 Hz gradual approach
    llm_monitor.py     # Gemini anomaly detector + scan cleaner
    navigate.py        # sends Nav2 goal
  launch/
    gazebo.launch.py       # Gazebo + TurtleBot3
    nav2.launch.py         # Nav2 using /scan  (baseline + attack)
    nav2_llm.launch.py     # Nav2 using /scan_verified  (defense)
  param/
    burger_verified.yaml   # Nav2 params pointing to /scan_verified
```
