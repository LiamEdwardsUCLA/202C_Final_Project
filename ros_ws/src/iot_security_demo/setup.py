from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'iot_security_demo'

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'param'), glob('param/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'navigate = iot_security_demo.navigate:main',
            'attacker = iot_security_demo.attacker:main',
            'attacker2 = iot_security_demo.attacker2:main',
            'attacker3 = iot_security_demo.attacker3:main',
            'attacker4 = iot_security_demo.attacker4:main',
            'rate_filter = iot_security_demo.rate_filter:main',
            'llm_monitor = iot_security_demo.llm_monitor:main',
        ],
    },
)
