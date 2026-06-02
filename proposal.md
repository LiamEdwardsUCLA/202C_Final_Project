## Final Project (202C IoT Securit)
For the project, we are asked to use LLM/agents to work on/experiment with some topic discussed in the class (sensor security, side channels, crypto, etc)

I want to use an agent to monitor a ROS2 network. In particular, our attack will be on a basic autonomous driving agent which is navigating an environment to reach a goal. By accessing the same network and publishing malicious scans at a higher frequency than the real scans (say 30Hz over the 10Hz real scans), the attacker tricks the bot into malicious movement. 

We use two methods to address this - first, a basic filter, then second a small LLM.