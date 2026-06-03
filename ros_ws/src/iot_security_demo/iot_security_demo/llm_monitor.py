"""
LLM-based LIDAR anomaly monitor (Defense 2).

Subscribes to /scan_filtered, batches recent scans, and asks Gemini every
POLL_INTERVAL seconds whether the data looks like a spoofing attack.
If an attack is detected, publishes a cleaned scan to /scan_verified with
the suspicious ranges replaced by inf (no obstacle).

Nav2 should be configured to use /scan_verified.
"""

import copy
import json
import math
import os
import threading
import datetime

import rclpy
import rclpy.parameter
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import Odometry

from google import genai
from google.genai import types

SENSOR_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.BEST_EFFORT,
    durability=DurabilityPolicy.VOLATILE,
)
PUB_QOS = QoSProfile(
    depth=10,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
)

POLL_INTERVAL = 10.0  # seconds between LLM queries
BUFFER_SIZE = 15  # number of recent scans to summarise
SECTOR_DEG = 60  # degrees per summary sector (6 sectors total)
RAY_HISTORY = 20  # per-ray rolling history depth for median cleaning
MODEL = "gemini-2.0-flash"


def sector_mins(ranges, angle_min, angle_increment, sector_deg=60):
    """Return min range per sector (list of 360/sector_deg values)."""
    n = len(ranges)
    num_sectors = 360 // sector_deg
    sector_size = int(round(math.radians(sector_deg) / angle_increment))
    result = []
    for s in range(num_sectors):
        start = (s * sector_size) % n
        vals = [ranges[(start + i) % n] for i in range(sector_size)]
        finite = [v for v in vals if math.isfinite(v) and v > 0]
        result.append(round(min(finite), 2) if finite else float("inf"))
    return result


SECTOR_LABELS = ["front", "front-left", "left", "rear", "right", "front-right"]

SYSTEM_PROMPT = """\
You are a security monitor for a mobile robot's 360° LIDAR sensor.
The sensor publishes scans at ~10 Hz. Each scan covers 360° with 1° resolution.
A known attack injects fake obstacle readings in the forward direction at a short \
range (typically 0.3–0.5 m), causing the robot to think there is a wall directly \
ahead when there is none. The fake readings may include noise and dropouts to \
appear more realistic.

You will receive scan summaries (minimum range per 60° sector) over a recent window \
and the robot's displacement. Determine whether a spoofing attack is occurring.

Signs of an attack:
- Sudden appearance of a close obstacle (< 0.6 m) in forward sectors that persists \
across many consecutive scans.
- The obstacle range stays roughly constant despite robot movement (a real obstacle \
would gradually change as the robot approaches or turns).
- Other sectors show normal, varying ranges inconsistent with the robot being boxed in.

If an attack is detected, also estimate the approximate range threshold: readings \
below this value in the suspicious sectors are likely fake, while readings at or \
above it (e.g. a real wall further away) should be preserved.

Respond ONLY with a JSON object — no markdown, no explanation outside the JSON:
{
  "attack_detected": <true|false>,
  "suspicious_sectors": [<list of sector labels from: front, front-left, \
front-right, left, right, rear>],
  "suspect_range_max": <float, metres — readings below this are likely fake, \
null if no attack>,
  "confidence": <"high"|"medium"|"low">,
  "reasoning": "<one or two sentences>"
}"""


class LLMMonitor(Node):
    def __init__(self, **kwargs):
        super().__init__("llm_monitor", **kwargs)

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            self.get_logger().error(
                "GEMINI_API_KEY not set — LLM monitor will not query Gemini"
            )
        self._client = genai.Client(api_key=api_key) if api_key else None

        self._lock = threading.Lock()
        self._scan_buffer = []  # list of (rel_time_s, sector_mins)
        self._ray_history = {}  # ray_idx -> list of recent range values
        self._t0 = None
        self._odom_start = None
        self._odom_latest = None
        self._latest_scan = None
        self._attack_active = False
        self._suspect_range_max = 0.6  # updated by Gemini response

        self.scan_sub = self.create_subscription(
            LaserScan, "/scan_filtered", self._scan_cb, SENSOR_QOS
        )
        self.odom_sub = self.create_subscription(Odometry, "/odom", self._odom_cb, 10)
        self.pub = self.create_publisher(LaserScan, "/scan_verified", PUB_QOS)

        self.create_timer(POLL_INTERVAL, self._poll)
        # Always forward latest scan (cleaned if attack active)
        self.create_timer(0.1, self._forward)

        log_dir = os.path.expanduser("~/202C_Final_Project/logs")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_path = os.path.join(log_dir, f"llm_monitor_{ts}.log")
        with open(self._log_path, "w") as f:
            f.write(f"LLM Monitor log — started {ts}\n")
            f.write(f"Model: {MODEL}  Poll interval: {POLL_INTERVAL}s\n")
            f.write("=" * 70 + "\n\n")

        self.get_logger().info(
            f"LLM monitor active — polling Gemini every {POLL_INTERVAL}s\n"
            f"  Conversation log: {self._log_path}"
        )

    # ------------------------------------------------------------------ #

    def _scan_cb(self, msg: LaserScan):
        with self._lock:
            self._latest_scan = msg
            now_s = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            if self._t0 is None:
                self._t0 = now_s
            rel = now_s - self._t0
            smins = sector_mins(
                msg.ranges, msg.angle_min, msg.angle_increment, SECTOR_DEG
            )
            self._scan_buffer.append((rel, smins))
            if len(self._scan_buffer) > BUFFER_SIZE:
                self._scan_buffer.pop(0)

            # Update per-ray rolling history
            for i, r in enumerate(msg.ranges):
                if math.isfinite(r) and r > 0:
                    hist = self._ray_history.setdefault(i, [])
                    hist.append(r)
                    if len(hist) > RAY_HISTORY:
                        hist.pop(0)

    def _odom_cb(self, msg: Odometry):
        with self._lock:
            pos = msg.pose.pose.position
            if self._odom_start is None:
                self._odom_start = (pos.x, pos.y)
            self._odom_latest = (pos.x, pos.y)

    # ------------------------------------------------------------------ #

    def _forward(self):
        with self._lock:
            msg = self._latest_scan
            attack = self._attack_active
            suspect_max = self._suspect_range_max
            ray_history = {k: list(v) for k, v in self._ray_history.items()}
        if msg is None:
            return
        if not attack:
            self.pub.publish(msg)
            return

        # Surgical cleaning: only replace rays that look fake.
        # A ray is fake if its current value is below suspect_max AND its
        # historical median was well above suspect_max (i.e. it appeared suddenly).
        # Rays that were already close historically (real wall) are preserved.
        cleaned = copy.deepcopy(msg)
        n = len(cleaned.ranges)
        center = int(round(-msg.angle_min / msg.angle_increment)) % n
        spread = int(round(math.radians(SECTOR_DEG) / msg.angle_increment))
        replaced = 0

        for offset in range(-spread, spread + 1):
            idx = (center + offset) % n
            current = cleaned.ranges[idx]
            if not math.isfinite(current) or current >= suspect_max:
                continue  # not suspicious

            hist = ray_history.get(idx, [])
            if len(hist) < 3:
                continue  # not enough history to judge

            hist_sorted = sorted(hist)
            median = hist_sorted[len(hist_sorted) // 2]

            if median > suspect_max * 1.5:
                # Historical median was much further — this reading is a sudden
                # jump, likely injected. Restore to historical median.
                cleaned.ranges[idx] = median
                replaced += 1
            # else: historically close too → real obstacle, leave it alone

        if replaced > 0:
            self.get_logger().info(
                f'Cleaned {replaced} suspicious rays (suspect_max={suspect_max:.2f} m)')
        self.pub.publish(cleaned)

    # ------------------------------------------------------------------ #

    def _poll(self):
        if self._client is None:
            return

        with self._lock:
            buffer = list(self._scan_buffer)
            odom_start = self._odom_start
            odom_latest = self._odom_latest

        if len(buffer) < 5:
            return

        # Build displacement string
        if odom_start and odom_latest:
            dx = odom_latest[0] - odom_start[0]
            dy = odom_latest[1] - odom_start[1]
            disp = f"{math.hypot(dx, dy):.2f} m"
        else:
            disp = "unknown"

        # Build compact scan table
        header = "  ".join(f"{l:>10}" for l in SECTOR_LABELS)
        rows = []
        for rel, smins in buffer:
            row = f"t={rel:5.1f}s  " + "  ".join(f"{v:>10.2f}" for v in smins)
            rows.append(row)

        snapshot = (
            f"Robot displacement over window: {disp}\n\n"
            f"Scan summaries (min range in metres per 60° sector):\n"
            f"          {header}\n" + "\n".join(rows)
        )

        self.get_logger().info("Querying Gemini...")
        threading.Thread(target=self._query, args=(snapshot,), daemon=True).start()

    def _query(self, snapshot: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        try:
            response = self._client.models.generate_content(
                model=MODEL,
                contents=snapshot,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            result = json.loads(raw)
        except Exception as e:
            self.get_logger().error(f"Gemini error: {e}")
            with open(self._log_path, "a") as f:
                f.write(f"[{ts}] ERROR: {e}\n\n")
            return

        with open(self._log_path, "a") as f:
            f.write(f"[{ts}] --- PROMPT ---\n{snapshot}\n\n")
            f.write(f"[{ts}] --- RESPONSE ---\n{json.dumps(result, indent=2)}\n\n")

        detected = result.get("attack_detected", False)
        confidence = result.get("confidence", "?")
        sectors = result.get("suspicious_sectors", [])
        reasoning = result.get("reasoning", "")

        if detected:
            suspect_max = result.get("suspect_range_max") or 0.6
            self.get_logger().warn(
                f"[ATTACK DETECTED] confidence={confidence} "
                f"sectors={sectors} suspect_range_max={suspect_max:.2f} m\n"
                f"  Reasoning: {reasoning}"
            )
            with self._lock:
                self._attack_active = True
                self._suspect_range_max = float(suspect_max)
        else:
            self.get_logger().info(f"[CLEAN] confidence={confidence} — {reasoning}")
            with self._lock:
                self._attack_active = False


def main():
    rclpy.init()
    node = LLMMonitor(
        parameter_overrides=[
            rclpy.parameter.Parameter(
                "use_sim_time",
                rclpy.parameter.Parameter.Type.BOOL,
                True,
            )
        ]
    )
    rclpy.spin(node)
    rclpy.shutdown()
