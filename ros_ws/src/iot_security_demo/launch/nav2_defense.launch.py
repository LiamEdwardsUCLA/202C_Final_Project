import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
import rclpy.parameter


def generate_launch_description():
    tb3_nav2 = get_package_share_directory('turtlebot3_navigation2')
    our_pkg = get_package_share_directory('iot_security_demo')

    map_file = os.path.join(tb3_nav2, 'map', 'map.yaml')
    params_file = os.path.join(our_pkg, 'param', 'burger_filtered.yaml')

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_nav2, 'launch', 'navigation2.launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'True',
            'map': map_file,
            'params_file': params_file,
        }.items()
    )

    return LaunchDescription([
        SetEnvironmentVariable('TURTLEBOT3_MODEL', 'burger'),
        nav2,
    ])
