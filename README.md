# Localization Using Particle Filter

We will implement a particle filter to localize a robot moving on a 2D map with several landmarks.

We use the Odometry motion model to estimate the robot movement. 

The measurement is obtained from a range-finder sensor, and it reports the distances to the landmarks. 

The world map and sensor data can be obtained from the data folder. 

By running the 'particle_filter.py', you can get the following results.

![alt text](mygif.gif)