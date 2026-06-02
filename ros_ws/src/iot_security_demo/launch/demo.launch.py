import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')
    tb3_nav2 = get_package_share_directory('turtlebot3_navigation2')
    map_file = os.path.join(tb3_nav2, 'map', 'map.yaml')

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_gazebo, 'launch', 'turtlebot3_world.launch.py')
        ),
        launch_arguments={
            'x_pose': '-2.0',
            'y_pose': '-0.5',
        }.items()
    )

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(tb3_nav2, 'launch', 'navigation2.launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'True',
            'map': map_file,
        }.items()
    )

    return LaunchDescription([
        SetEnvironmentVariable('TURTLEBOT3_MODEL', 'burger'),
        gazebo,
        nav2,
    ])
