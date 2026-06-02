import rclpy
from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
from geometry_msgs.msg import PoseStamped


def make_pose(navigator, x, y, w=1.0):
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.header.stamp = navigator.get_clock().now().to_msg()
    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.orientation.w = w
    return pose


def main():
    rclpy.init()
    navigator = BasicNavigator()

    # Match the spawn pose in demo.launch.py
    navigator.setInitialPose(make_pose(navigator, -2.0, -0.5))
    navigator.waitUntilNav2Active()

    print('Nav2 active — sending goal')
    goal = make_pose(navigator, 2.0, 0.0)
    navigator.goToPose(goal)

    while not navigator.isTaskComplete():
        feedback = navigator.getFeedback()
        if feedback:
            dist = feedback.distance_remaining
            print(f'  Distance remaining: {dist:.2f} m', end='\r')

    result = navigator.getResult()
    if result == TaskResult.SUCCEEDED:
        print('\nGoal reached!')
    else:
        print(f'\nNavigation failed: {result}')

    navigator.lifecycleShutdown()
    rclpy.shutdown()
