# LLM-Assisted LIDAR Spoofing Detection in ROS2 (ECE 202C Final Project)

## Overview
We demonstrate a LIDAR spoofing attack on a simulated autonomous robot and develop two defenses — a classical rate filter and an LLM-based anomaly monitor — showing the limitations of each and how the LLM defense handles attacks the filter cannot.

## System
A TurtleBot3 Burger navigates autonomously in a Gazebo simulation using the Nav2 stack with AMCL localization. The robot receives 360° LIDAR scans at ~10 Hz on the ROS2 `/scan` topic and plans paths to a goal using a pre-built map.

## Attack Scenarios

**Attack 1 — Frequency flood (30 Hz):**
An attacker node joins the ROS2 network and publishes fake LIDAR scans at 30 Hz — 3× the real sensor rate. Each fake scan injects a phantom wall directly in front of the robot at ~0.35 m. Nav2's costmap accepts all messages regardless of source, so the fake wall dominates and the robot cannot navigate.

**Attack 2 — Timestamp-spoofed (10 Hz, bypasses rate filter):**
A smarter attacker publishes at ~10 Hz but stamps each message 80 ms ahead of the real scan. This exploits the rate filter's threshold: the spoofed scan passes (80 ms > 67 ms minimum interval) while the next real scan is dropped (arriving only 20 ms later). The robot sees mostly fake data at the normal sensor rate.

**Attack 3 — Noisy wall (10 Hz, bypasses rate filter):**
An extension of Attack 2 that adds per-ray Gaussian noise, random dropouts, and arc-width jitter to the fake wall, making it look more like a real rough surface and harder for both simple heuristics and the LLM to classify confidently.

## Defense 1 — Rate Filter
A relay node subscribes to `/scan` and forwards messages to `/scan_filtered` only if the interval between consecutive message timestamps exceeds 67 ms (enforcing a 15 Hz ceiling). Nav2 is reconfigured to use `/scan_filtered`.

- **Succeeds against:** Attack 1 (drops 2/3 of flood messages)
- **Fails against:** Attacks 2 and 3 (spoofed timestamps pass the interval check)

## Defense 2 — LLM Monitor (Gemini)
A monitor node sits downstream of the rate filter, subscribing to `/scan_filtered` and publishing to `/scan_verified`. Every 10 seconds it sends Gemini 2.0 Flash a compact snapshot: minimum range per 60° sector over the last 15 scans, plus robot displacement from odometry. Gemini returns structured JSON indicating whether an attack is detected, which sectors are suspicious, the estimated fake-range threshold, and its reasoning.

When an attack is detected, the monitor performs **surgical cleaning** rather than blindly zeroing the forward arc:
- Each ray in suspicious sectors is compared to its rolling median over the last 20 scans
- Rays that suddenly jumped close (current < threshold AND historical median > 1.5× threshold) are replaced with their historical median — restoring the pre-attack view
- Rays that were historically close (robot genuinely near a real wall) are left untouched

Nav2 is reconfigured to use `/scan_verified`.

- **Succeeds against:** Attacks 1, 2, and 3
- **Key advantage over the rate filter:** reasons about *content* and *temporal plausibility*, not just message frequency

## Topic Pipeline
```
/scan  →  [rate_filter]  →  /scan_filtered  →  [llm_monitor]  →  /scan_verified  →  Nav2
```
