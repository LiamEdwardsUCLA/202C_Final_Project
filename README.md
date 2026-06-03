# LLM-Assisted LIDAR Spoofing Detection in ROS2

ECE 202C — IoT Security Final Project

Demonstrates LIDAR spoofing attacks on a simulated autonomous robot and two defenses: a classical rate filter and a Gemini-based anomaly monitor.

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
- A Gemini API key (for Defense 2 only)

---

## Build

```bash
cd ~/202C_Final_Project/ros_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
```

---

## Scenarios

All scripts open separate terminal windows for each component and wait for each layer to be ready before starting the next.

### Baseline — robot navigates normally

```bash
./run.sh
```

Starts Gazebo, Nav2, and sends a navigation goal from (-2, -0.5) to (2, 0). No attack, no defense.

---

### Attack 1 — Frequency flood (30 Hz, no defense)

```bash
./run_attack1.sh
```

Nav2 reads `/scan` directly. The flood attacker launches automatically once the robot starts moving. The robot stops and cannot navigate.

---

### Defense 1 — Rate filter blocks Attack 1

```bash
./run_defense1.sh
```

Rate filter enforces ≤ 15 Hz on `/scan_filtered`. Attack 1 launches automatically — the robot ignores it and navigates normally.

---

### Attack 2 — Timestamp-spoofed (bypasses rate filter)

```bash
./run_attack2.sh
```

Same rate filter setup, but launches `attacker2` instead. Spoofed timestamps slip past the filter (zero drops logged) — robot is still blocked.

---

### Attack 3 — Noisy wall (bypasses rate filter)

```bash
./run_attack3.sh
```

Same as Attack 2 but with per-ray Gaussian noise, dropouts, and arc jitter to look more like a real surface.

---

### Defense 2 — LLM monitor catches Attacks 2 & 3

```bash
export GEMINI_API_KEY=your_key_here
./run_defense2.sh                        # default: attacker3
ATTACKER=attacker2 ./run_defense2.sh     # use attacker2 instead
```

Adds the LLM monitor downstream of the rate filter:

```
/scan → rate_filter → /scan_filtered → llm_monitor → /scan_verified → Nav2
```

Every 10 seconds the monitor sends Gemini a snapshot of recent scan data and robot odometry. If an attack is detected, suspicious rays are restored to their historical median (preserving real obstacles). Conversation logs are written to `~/202C_Final_Project/logs/`.

---

## Topic Pipeline

| Scenario | Topics |
|---|---|
| No defense | `/scan` → Nav2 |
| Defense 1 | `/scan` → `rate_filter` → `/scan_filtered` → Nav2 |
| Defense 2 | `/scan` → `rate_filter` → `/scan_filtered` → `llm_monitor` → `/scan_verified` → Nav2 |

---

## Nodes

| Node | Command | Description |
|---|---|---|
| `attacker` | `ros2 run iot_security_demo attacker` | Flood attack at 30 Hz |
| `attacker2` | `ros2 run iot_security_demo attacker2` | Timestamp-spoofed at ~10 Hz |
| `attacker3` | `ros2 run iot_security_demo attacker3` | Noisy timestamp-spoofed at ~10 Hz |
| `rate_filter` | `ros2 run iot_security_demo rate_filter` | Rate-based relay filter |
| `llm_monitor` | `ros2 run iot_security_demo llm_monitor` | Gemini anomaly monitor |
| `navigate` | `ros2 run iot_security_demo navigate` | Send navigation goal |

---

## Project Structure

```
ros_ws/src/iot_security_demo/
  iot_security_demo/
    attacker.py        # Attack 1: 30 Hz flood
    attacker2.py       # Attack 2: timestamp-spoofed 10 Hz
    attacker3.py       # Attack 3: noisy timestamp-spoofed 10 Hz
    rate_filter.py     # Defense 1: rate-based relay
    llm_monitor.py     # Defense 2: Gemini anomaly monitor
    navigate.py        # Nav2 goal sender
  launch/
    gazebo.launch.py        # Gazebo + TurtleBot3
    nav2.launch.py          # Nav2 (baseline, uses /scan)
    nav2_defense.launch.py  # Nav2 with rate filter (uses /scan_filtered)
    nav2_llm.launch.py      # Nav2 with LLM defense (uses /scan_verified)
  param/
    burger_filtered.yaml    # Nav2 params pointing to /scan_filtered
    burger_verified.yaml    # Nav2 params pointing to /scan_verified
```
