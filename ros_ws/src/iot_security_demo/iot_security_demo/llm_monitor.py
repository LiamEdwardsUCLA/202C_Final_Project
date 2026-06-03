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
from nav2_msgs.srv import ClearEntireCostmap

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
MODEL = "gemini-3.1-flash-preview"


def sector_stats(ranges, angle_min, angle_increment, sector_deg=60):
    """Return (mins, stds) — min range and std dev per sector."""
    n = len(ranges)
    num_sectors = 360 // sector_deg
    sector_size = int(round(math.radians(sector_deg) / angle_increment))
    mins, stds = [], []
    for s in range(num_sectors):
        start = (s * sector_size) % n
        vals = [ranges[(start + i) % n] for i in range(sector_size)]
        finite = [v for v in vals if math.isfinite(v) and v > 0]
        if finite:
            mn = min(finite)
            mean = sum(finite) / len(finite)
            std = math.sqrt(sum((v - mean) ** 2 for v in finite) / len(finite))
            mins.append(round(mn, 2))
            stds.append(round(std, 3))
        else:
            mins.append(float("inf"))
            stds.append(0.0)
    return mins, stds


SECTOR_LABELS = ["front", "front-left", "left", "rear", "right", "front-right"]

SYSTEM_PROMPT = """\
You are a security monitor for a mobile robot's 360° LIDAR sensor. Determine \
whether the sensor data contains injected spoofed readings or is consistent with \
normal navigation in a real environment.

Each scan entry shows per 60° sector: the minimum range observed and the \
within-scan standard deviation of ranges (format: min ± std, in metres). \
The robot's total displacement over the window is also provided.

Real LIDAR behaviour in a physical environment:
- Ranges change as the robot moves; walls can appear or disappear quickly at \
  corners; the robot may follow a wall at a consistent distance for several scans.
- Within a single scan, std dev reflects the geometry of that sector — a nearby \
  flat wall produces low std dev naturally.
- Scan-to-scan variation in both the min and std values is normal due to sensor \
  noise, surface texture, and small robot movements.

Spoofed readings tend to have a different character: an injected signal is \
generated synthetically and often lacks the organic variation of a real surface. \
Look for patterns that seem inconsistent with how a real robot moving through a \
real environment would produce data — consider the robot's motion, the \
consistency of readings across time, and whether any sector behaves differently \
from the others in a way that is hard to explain physically.

If an attack is detected, estimate the range below which readings in the \
suspicious sectors are likely fake.

Respond ONLY with a JSON object — no markdown, no explanation outside the JSON:
{
  "attack_detected": <true|false>,
  "suspicious_sectors": [<list of sector labels from: front, front-left, \
front-right, left, right, rear>],
  "suspect_range_max": <float, metres — readings below this are fake, \
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
        self._scan_buffer = []  # list of (rel_time_s, smins, sstds, (x, y))
        self._ray_history = {}  # ray_idx -> list of recent range values
        self._t0 = None
        self._odom_latest = None
        self._latest_scan = None
        self._attack_active = False
        self._attack_just_detected = False
        self._last_reasoning = None  # carry forward between queries
        self._suspect_range_max = 0.6

        self._local_clear = self.create_client(
            ClearEntireCostmap, "/local_costmap/clear_entirely_local_costmap"
        )
        self._global_clear = self.create_client(
            ClearEntireCostmap, "/global_costmap/clear_entirely_global_costmap"
        )

        self.scan_sub = self.create_subscription(
            LaserScan, "/scan", self._scan_cb, SENSOR_QOS
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
            smins, sstds = sector_stats(
                msg.ranges, msg.angle_min, msg.angle_increment, SECTOR_DEG
            )
            pos = self._odom_latest or (0.0, 0.0, 0.0)
            self._scan_buffer.append((rel, smins, sstds, pos))
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
            q = msg.pose.pose.orientation
            siny = 2.0 * (q.w * q.z + q.x * q.y)
            cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
            yaw_deg = math.degrees(math.atan2(siny, cosy))
            self._odom_latest = (pos.x, pos.y, yaw_deg)

    # ------------------------------------------------------------------ #

    def _forward(self):
        with self._lock:
            msg = self._latest_scan
            attack = self._attack_active
            just_detected = self._attack_just_detected
            suspect_max = self._suspect_range_max
            ray_history = {k: list(v) for k, v in self._ray_history.items()}
            if just_detected:
                self._attack_just_detected = False
        if msg is None:
            return

        # One-shot costmap clear on first detection
        if just_detected:
            threading.Thread(target=self._clear_costmaps, daemon=True).start()

        if not attack:
            self.pub.publish(msg)
            return

        # Surgical cleaning: for each suspicious ray, use the max of its history
        # (which captures pre-attack real readings even if history is partly
        # corrupted). Fall back to inf if the entire history is fake.
        # Use 1.3× suspect_max as the cleaning threshold to catch noisy fake
        # readings that land slightly above Gemini's estimate.
        cleaned = copy.deepcopy(msg)
        n = len(cleaned.ranges)
        center = int(round(-msg.angle_min / msg.angle_increment)) % n
        # Clean ±75° to also catch arc-jitter that spills outside the ±60° sector
        spread = int(round(math.radians(75) / msg.angle_increment))
        clean_threshold = suspect_max * 2.0
        replaced = 0

        for offset in range(-spread, spread + 1):
            idx = (center + offset) % n
            current = cleaned.ranges[idx]
            if not math.isfinite(current) or current >= clean_threshold:
                continue

            hist = ray_history.get(idx, [])
            best = max((v for v in hist if v > clean_threshold), default=None)
            if best is not None:
                cleaned.ranges[idx] = best  # restore to furthest real reading
            else:
                cleaned.ranges[idx] = float("inf")  # no real history — force clear
            replaced += 1

        if replaced > 0:
            self.get_logger().info(
                f"Cleaned {replaced} rays (suspect_max={suspect_max:.2f} m)"
            )
        self.pub.publish(cleaned)

    def _clear_costmaps(self):
        req = ClearEntireCostmap.Request()
        for client, name in [
            (self._local_clear, "local"),
            (self._global_clear, "global"),
        ]:
            if client.wait_for_service(timeout_sec=2.0):
                client.call(req)
                self.get_logger().info(f"Cleared {name} costmap")
            else:
                self.get_logger().warn(f"{name} costmap clear service not available")

    # ------------------------------------------------------------------ #

    def _poll(self):
        if self._client is None:
            return

        with self._lock:
            buffer = list(self._scan_buffer)
            last_reasoning = self._last_reasoning

        if len(buffer) < 5:
            return

        # Displacement from first to last scan in the buffer window
        p0 = buffer[0][3]
        p1 = buffer[-1][3]
        disp = f"{math.hypot(p1[0] - p0[0], p1[1] - p0[1]):.2f} m"

        # Build compact scan table with pose + min±std per sector
        sector_header = "  ".join(f"{label:>14}" for label in SECTOR_LABELS)
        rows = []
        for rel, smins, sstds, pose in buffer:
            x, y, hdg = pose
            pose_str = f"({x:5.2f},{y:5.2f}) hdg={hdg:+6.1f}°"
            cells = "  ".join(f"{mn:>6.2f}±{sd:>5.3f}" for mn, sd in zip(smins, sstds))
            rows.append(f"t={rel:5.1f}s  {pose_str}  {cells}")

        prior = (
            f"Your previous assessment: {last_reasoning}\n\n" if last_reasoning else ""
        )

        snapshot = (
            prior
            + f"Robot displacement over scan window: {disp}\n\n"
            + "Scan summaries — format: (x,y) heading  |  min_range ± within-scan std (metres):\n"
            + f"                                               {sector_header}\n"
            + "\n".join(rows)
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
        summary = f"{'ATTACK DETECTED' if detected else 'CLEAN'}, confidence={confidence} — {reasoning}"

        if detected:
            suspect_max = result.get("suspect_range_max") or 0.6
            self.get_logger().warn(
                f"[ATTACK DETECTED] confidence={confidence} "
                f"sectors={sectors} suspect_range_max={suspect_max:.2f} m\n"
                f"  Reasoning: {reasoning}"
            )
            with self._lock:
                if not self._attack_active:
                    self._attack_just_detected = True
                self._attack_active = True
                self._suspect_range_max = float(suspect_max)
                self._last_reasoning = summary
        else:
            self.get_logger().info(f"[CLEAN] confidence={confidence} — {reasoning}")
            with self._lock:
                self._attack_active = False
                self._last_reasoning = summary


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
