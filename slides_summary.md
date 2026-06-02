# Slide Deck Summary — LLM-Assisted LIDAR Spoofing Detection
## ECE 202C Final Project — ~4 minute presentation

---

### Slide 1: Title
**LLM-Assisted LIDAR Spoofing Detection in ROS2**
ECE 202C — IoT Security
[Student name(s)]

---

### Slide 2: Motivation & Setup
**What we built:**
- TurtleBot3 robot navigating autonomously in Gazebo simulation using Nav2 + AMCL
- Robot receives 360° LIDAR scans at 10 Hz, plans paths to a goal on a known map
- ROS2 network: any node can publish to any topic — no authentication

**The threat:** An attacker with network access can inject fake sensor data. How bad can it be, and can an LLM catch it?

---

### Slide 3: The Attack — LIDAR Spoofing
**Core idea:** Publish fake scans showing a phantom wall 0.35 m in front of the robot. Nav2's costmap accepts messages from any publisher — it has no way to verify the source.

**Attack 1 — Frequency flood:**
- Attacker publishes fake scans at 30 Hz (real sensor: 10 Hz)
- Fake data dominates; robot is completely blocked

[DEMO VIDEO: Attack 1 — robot stops and spins in place]

**Why this works:** ROS2 pub/sub has no authentication. The costmap marks the fake obstacle as real.

---

### Slide 4: Defense 1 — Rate Filter
**Idea:** If messages arrive faster than the sensor's known rate, they must be injections.

- Relay node between `/scan` and `/scan_filtered`
- Drops any message arriving less than 67 ms after the previous one (enforces ≤ 15 Hz ceiling)
- Nav2 reconfigured to listen to `/scan_filtered`

**Result:** Blocks Attack 1 completely ✓

[DEMO VIDEO: Rate filter — attacker running, robot navigates normally]

**The limitation:** A smarter attacker can match the expected frequency.

---

### Slide 5: Attack 2 — Bypassing the Rate Filter
**Timestamp spoofing:**
- Attacker reads each real scan, stamps the fake version 80 ms ahead
- 80 ms > 67 ms threshold → rate filter passes it
- Next real scan arrives only 20 ms later → rate filter drops it
- Robot sees mostly fake data at a perfectly normal rate

**Attack 3 — Noisy wall:**
- Same timing trick, but adds per-ray Gaussian noise, random dropouts, arc-width jitter
- Looks more like a real rough surface — harder to classify

[DEMO VIDEO: Attack 2/3 — rate filter shows zero drops, robot still blocked]

---

### Slide 6: Defense 2 — LLM Monitor
**Key insight:** The rate filter checks *when* messages arrive. An LLM can check *what they say* and whether it makes physical sense.

**Architecture:**
```
/scan → rate_filter → /scan_filtered → llm_monitor → /scan_verified → Nav2
```

**Every 10 seconds**, the monitor sends Gemini 2.0 Flash:
- Min range per 60° sector over the last 15 scans
- Robot displacement from odometry

**Gemini returns JSON:** attack detected, suspicious sectors, estimated fake-range threshold, reasoning

---

### Slide 7: Surgical Cleaning
**Problem with naive cleaning:** zeroing the entire forward arc would hide real walls too.

**Our approach — per-ray median restoration:**
- Track 20-scan rolling history for each of the 360 rays
- When attack detected: for each suspicious ray, compare current value to its historical median
- **Suddenly close** (current < threshold, median > 1.5× threshold) → replace with median
- **Historically close** (robot near a real wall) → leave untouched

Result: fake obstacles removed, real obstacles preserved, robot can navigate safely.

[DEMO VIDEO: LLM defense — attacker3 running, Gemini detects it, robot resumes navigating]

---

### Slide 8: Results & Takeaways

| | Attack 1 (30 Hz flood) | Attack 2 (spoofed 10 Hz) | Attack 3 (noisy wall) |
|---|---|---|---|
| No defense | ✗ blocked | ✗ blocked | ✗ blocked |
| Rate filter | ✓ passes | ✗ blocked | ✗ blocked |
| LLM monitor | ✓ passes | ✓ passes | ✓ passes |

**Key takeaways:**
- ROS2 networks have no built-in sensor authentication — spoofing is trivial
- Rate-based filters are bypassable with simple timestamp manipulation
- LLMs can perform temporal plausibility reasoning that classical filters cannot
- Surgical cleaning matters: a naive "zero it out" response could itself cause harm

---

### Slide 9: Limitations & Future Work
- LLM polling at 10s introduces latency — robot is affected for up to 10s before detection
- Cleaning assumes the attack is in the forward arc — a smarter attacker could target other directions
- Gemini reasoning quality depends on prompt; the approach generalizes to other sensors (IMU, GPS, cameras)
- Future: continuous per-scan inference with a lightweight local model; multi-sensor fusion for corroboration
