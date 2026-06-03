"""
Attacker 4: rotating wall at sensor rate (~5 Hz).

A clean ±45° arc obstacle that shifts its center angle by 15° per scan,
cycling around the robot. The robot can't route around it because any planned
path gets blocked. Hard to detect because the obstacle's position changes
each scan — the LLM must recognise that a wall rotating around a stationary
robot is physically impossible.
"""

import copy
import math
import random
import rclpy
import rclpy.parameter
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan

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

WALL_HALF_DEG  = 30
ROTATE_DEG     = 45
SCANS_PER_MOVE = 5
RANGE_MIN      = 0.25
RANGE_MAX      = 0.55
NOISE_STD      = 0.04   # per-ray Gaussian noise to avoid zero std dev
DROPOUT_PROB   = 0.08   # chance a ray keeps the real value


class Attacker4(Node):
    def __init__(self, **kwargs):
        super().__init__("lidar_attacker4", **kwargs)
        self._center_deg = 0.0
        self._current_range = RANGE_MIN
        self._scan_count = 0
        self.sub = self.create_subscription(LaserScan, "/scan", self._cb, SENSOR_QOS)
        self.pub = self.create_publisher(LaserScan, "/scan", PUB_QOS)
        self.get_logger().info(
            f"Attacker 4: rotating wall ±{WALL_HALF_DEG}°, "
            f"jumps {ROTATE_DEG}° every {SCANS_PER_MOVE} scans, "
            f"range varies {RANGE_MIN}–{RANGE_MAX} m"
        )

    def _cb(self, msg: LaserScan):
        n           = len(msg.ranges)
        increment   = msg.angle_increment
        forward_idx = int(round(-msg.angle_min / increment)) % n
        center      = (forward_idx + int(round(
                        math.radians(self._center_deg) / increment))) % n
        spread      = int(round(math.radians(WALL_HALF_DEG) / increment))

        fake = copy.deepcopy(msg)
        fake.header.stamp = self.get_clock().now().to_msg()
        for off in range(-spread, spread + 1):
            if random.random() < DROPOUT_PROB:
                continue
            noisy = self._current_range + random.gauss(0, NOISE_STD)
            fake.ranges[(center + off) % n] = max(msg.range_min + 0.01, noisy)

        self.pub.publish(fake)

        self._scan_count += 1
        if self._scan_count >= SCANS_PER_MOVE:
            self._scan_count = 0
            self._center_deg = (self._center_deg + ROTATE_DEG) % 360
            self._current_range = random.uniform(RANGE_MIN, RANGE_MAX)
            self.get_logger().info(
                f"  wall jumped to {self._center_deg:.0f}°, "
                f"range={self._current_range:.2f} m"
            )


def main():
    rclpy.init()
    node = Attacker4(
        parameter_overrides=[
            rclpy.parameter.Parameter(
                "use_sim_time", rclpy.parameter.Parameter.Type.BOOL, True
            )
        ]
    )
    rclpy.spin(node)
    rclpy.shutdown()
