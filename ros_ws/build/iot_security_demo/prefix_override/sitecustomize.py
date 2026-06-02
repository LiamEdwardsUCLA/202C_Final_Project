import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/liamedwards/202C_Final_Project/ros_ws/install/iot_security_demo'
