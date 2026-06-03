import time as _time
from collections import deque

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

WINDOW_S = 1.0       # sliding window duration
MAX_PER_WINDOW = 12  # allow up to 12 messages/sec (real sensor ~5 Hz)


class RateFilter(Node):
    def __init__(self, **kwargs):
        super().__init__('rate_filter', **kwargs)
        self._window = deque()  # wall-clock receive times of passed messages
        self._dropped = 0
        self._passed = 0
        self._total = 0

        self.sub = self.create_subscription(
            LaserScan, '/scan', self._cb, SENSOR_QOS)
        self.pub = self.create_publisher(
            LaserScan, '/scan_filtered', PUB_QOS)

        self.create_timer(5.0, self._log_stats)
        self.get_logger().info(
            f'Rate filter active: max {MAX_PER_WINDOW} msgs/{WINDOW_S}s window, '
            'forwarding to /scan_filtered')

    def _cb(self, msg: LaserScan):
        self._total += 1
        now = _time.monotonic()

        # Evict timestamps outside the window
        while self._window and now - self._window[0] > WINDOW_S:
            self._window.popleft()

        if len(self._window) >= MAX_PER_WINDOW:
            self._dropped += 1
            return

        self._window.append(now)
        self._passed += 1
        self.pub.publish(msg)

    def _log_stats(self):
        self.get_logger().info(
            f'Stats — received={self._total}, passed={self._passed}, '
            f'dropped={self._dropped} in last 5s')
        self._total = 0
        self._passed = 0
        self._dropped = 0


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
