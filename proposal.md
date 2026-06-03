# LLM-Assisted LIDAR Spoofing Detection in ROS2 (ECE 202C Final Project)

## Overview
We demonstrate a series of LIDAR spoofing attacks on a simulated autonomous robot and defend against them using a Gemini-based anomaly monitor. The core question: can an LLM reason about the *plausibility* of sensor data and detect injected fake readings that evade classical approaches?

## System
A TurtleBot3 Burger navigates autonomously in a Gazebo simulation using the Nav2 stack with AMCL localization. The robot receives 360° LIDAR scans at ~5 Hz on the ROS2 `/scan` topic and plans paths to a goal using a pre-built map. Because ROS2 has no publisher authentication, any node on the network can publish to any topic.

## Attack Scenarios

**Attack 1 — Simple flood (30 Hz):**
An attacker node publishes fake scans at 30 Hz showing a phantom wall at ~0.35 m directly ahead. Nav2's costmap accepts messages from any publisher — the fake wall dominates and the robot cannot navigate.

**Attack 2 — Frequency-matched clean wall (~5 Hz):**
The attacker publishes one fake scan per real sensor scan, matching the sensor rate. No rate-based filter can distinguish this from legitimate data. The fake wall is a clean ±60° arc at fixed range.

**Attack 3 — Frequency-matched noisy wall (~5 Hz):**
Same as Attack 2, but adds per-ray Gaussian noise (σ=6 cm), random ray dropouts (12%), and arc-width jitter (±8°) to make the wall look like a real rough surface.

**Attack 4 — Gradual approach (~5 Hz):**
The fake obstacle starts at 2.0 m and "approaches" to 0.35 m at 0.15 m per scan, mimicking a real obstacle moving toward the robot. Physically implausible because the robot is not moving — requires the LLM to correlate scan changes with odometry to detect it.

## Defense — LLM Monitor (Gemini)

A monitor node subscribes to `/scan` and publishes to `/scan_verified`. Nav2 is reconfigured to use `/scan_verified`. Every 10 seconds the monitor sends Gemini 2.0 Flash a compact snapshot:
- Minimum range per 60° sector over the last 15 scans
- Robot displacement from odometry over the window

Gemini returns structured JSON: attack detected (bool), suspicious sectors, estimated fake-range threshold, confidence, and reasoning.

When an attack is detected, the monitor performs **surgical cleaning** rather than blindly zeroing the forward arc:
- Each ray in suspicious sectors is compared to its rolling median over the last 20 scans
- Rays that suddenly appeared close (current < threshold AND historical median > 1.5× threshold) are replaced with their historical median
- Rays that were historically close (robot genuinely near a real wall) are left untouched

This preserves real obstacles while removing injected ones. The robot resumes navigating.

## Topic Pipeline
```
/scan  →  [llm_monitor]  →  /scan_verified  →  Nav2
```

## Key Insight
Classical defenses (rate limiting, threshold rules) check *when* or *how often* data arrives. They fail against attackers who match the expected rate or disguise their pattern. An LLM can reason about *what the data says* and whether it is physically consistent with the robot's motion — a fundamentally different and more robust signal.
