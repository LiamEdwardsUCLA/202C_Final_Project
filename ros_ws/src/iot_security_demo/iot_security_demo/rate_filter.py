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

MAX_RATE_HZ = 15.0  # real sensor is ~10 Hz; anything faster is suspicious


class RateFilter(Node):
    def __init__(self, **kwargs):
        super().__init__('rate_filter', **kwargs)
        self._last_stamp = None
        self._min_interval_ns = int(1e9 / MAX_RATE_HZ)
        self._dropped = 0
        self._passed = 0

        self.sub = self.create_subscription(
            LaserScan, '/scan', self._cb, SENSOR_QOS)
        self.pub = self.create_publisher(
            LaserScan, '/scan_filtered', PUB_QOS)

        self.get_logger().info(
            f'Rate filter active: passing ≤{MAX_RATE_HZ} Hz, '
            'forwarding to /scan_filtered')

    def _cb(self, msg: LaserScan):
        stamp_ns = msg.header.stamp.sec * 10**9 + msg.header.stamp.nanosec

        if self._last_stamp is not None:
            interval_ns = stamp_ns - self._last_stamp
            if interval_ns < self._min_interval_ns:
                self._dropped += 1
                if self._dropped % 50 == 0:
                    self.get_logger().warn(
                        f'Dropping high-rate scans '
                        f'(dropped={self._dropped}, passed={self._passed})')
                return

        self._last_stamp = stamp_ns
        self._passed += 1
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = RateFilter(parameter_overrides=[
        rclpy.parameter.Parameter(
            'use_sim_time',
            rclpy.parameter.Parameter.Type.BOOL,
            True,
        )
    ])
    rclpy.spin(node)
    rclpy.shutdown()
