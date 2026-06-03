"""
Attacker 3: noisy wall at sensor rate (~5 Hz).
Per-ray Gaussian noise, random dropouts, arc-width jitter — looks like a rough surface.
"""
import copy
import math
import random
import rclpy
import rclpy.parameter
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan

SENSOR_QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT,
                        durability=DurabilityPolicy.VOLATILE)
PUB_QOS    = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                        durability=DurabilityPolicy.VOLATILE)

WALL_BASE_RANGE = 0.40
WALL_HALF_DEG   = 60
NOISE_STD       = 0.06
DROPOUT_PROB    = 0.12
ARC_JITTER_DEG  = 8


class Attacker3(Node):
    def __init__(self, **kwargs):
        super().__init__('lidar_attacker3', **kwargs)
        self.sub = self.create_subscription(LaserScan, '/scan', self._cb, SENSOR_QOS)
        self.pub = self.create_publisher(LaserScan, '/scan', PUB_QOS)
        self.get_logger().info('Attacker 3: noisy wall, ~5 Hz (frequency-matched)')

    def _cb(self, msg: LaserScan):
        n          = len(msg.ranges)
        center     = int(round(-msg.angle_min / msg.angle_increment)) % n
        base       = int(round(math.radians(WALL_HALF_DEG) / msg.angle_increment))
        jitter     = int(round(math.radians(
            random.uniform(-ARC_JITTER_DEG, ARC_JITTER_DEG)) / msg.angle_increment))
        spread     = max(10, base + jitter)
        fake       = copy.deepcopy(msg)
        fake.header.stamp = self.get_clock().now().to_msg()
        for off in range(-spread, spread + 1):
            idx = (center + off) % n
            if random.random() < DROPOUT_PROB:
                continue
            fake.ranges[idx] = max(msg.range_min + 0.01,
                                   WALL_BASE_RANGE + random.gauss(0, NOISE_STD))
        self.pub.publish(fake)


def main():
    rclpy.init()
    node = Attacker3(parameter_overrides=[
        rclpy.parameter.Parameter('use_sim_time', rclpy.parameter.Parameter.Type.BOOL, True)
    ])
    rclpy.spin(node)
    rclpy.shutdown()
