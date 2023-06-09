import numpy as np
import scipy.stats
import matplotlib.pyplot as plt
import imageio
import os
from helpler_readdata import read_world_map, read_sensor_measurement

#add random seed for generating comparable pseudo random numbers
np.random.seed(123)

#plot preferences, interactive plotting mode
plt.axis([-1, 12, 0, 10])
plt.ion()
plt.show()

def plot(particles, landmarks, map_limits, filename):
    # Visualizes the state of the particle filter.
    # Displays the particle set, mean position and landmarks.
    
    xs = []
    ys = []

    for particle in particles:
        xs.append(particle['x'])
        ys.append(particle['y'])

    # landmark positions
    lx=[]
    ly=[]

    for i in range (len(landmarks)):
        lx.append(landmarks[i+1][0])
        ly.append(landmarks[i+1][1])

    # mean pose as current estimate
    estimated_pose = mean_pose(particles)

    # plot filter state
    plt.clf()
    plt.plot(xs, ys, 'r.')
    plt.plot(lx, ly, 'bo', markersize=10, label='landmarks')
    plt.quiver(estimated_pose[0],
               estimated_pose[1],
               np.cos(estimated_pose[2]),
               np.sin(estimated_pose[2]),
               angles='xy', scale_units='xy', label='estimated mean')
    plt.axis(map_limits)
    plt.legend()
    plt.pause(0.02)
    plt.savefig(filename)

def generate_particles(num_particles, map_limits):
    # randomly initialize the particles inside the map limits

    particles = []

    for i in range(num_particles):
        particle = dict()

        # draw x,y and theta coordinate from uniform distribution
        # inside map limits
        particle['x'] = np.random.uniform(map_limits[0], map_limits[1])
        particle['y'] = np.random.uniform(map_limits[2], map_limits[3])
        particle['theta'] = np.random.uniform(-np.pi, np.pi)

        particles.append(particle)

    return particles

def mean_pose(particles):
    # calculate the mean pose of a particle set.
    # for x and y, the mean position is the mean of the particle coordinates
    # for theta, we cannot simply average the angles because of the wraparound 
    # (jump from -pi to pi). Therefore, we generate unit vectors from the 
    # angles and calculate the angle of their average 

    # save x and y coordinates of particles
    xs = []
    ys = []

    # save unit vectors corresponding to particle orientations 
    vxs_theta = []
    vys_theta = []

    for particle in particles:
        xs.append(particle['x'])
        ys.append(particle['y'])

        # make unit vector from particle orientation
        vxs_theta.append(np.cos(particle['theta']))
        vys_theta.append(np.sin(particle['theta']))

    # calculate average coordinates
    mean_x = np.mean(xs)
    mean_y = np.mean(ys)
    mean_theta = np.arctan2(np.mean(vys_theta), np.mean(vxs_theta))

    return [mean_x, mean_y, mean_theta]

def sample_motion(odometry, particles):
    # Samples new particle positions, based on old positions, the odometry
    # measurements and the motion noise 
    # (probabilistic motion models slide 27)

    delta_rot1 = odometry['r1']
    delta_trans = odometry['t']
    delta_rot2 = odometry['r2']

    # the motion noise parameters: [alpha1, alpha2, alpha3, alpha4]
    noise = [0.1, 0.1, 0.05, 0.05]

    # generate new particle set after motion update
    new_particles = []

    sigma_delta_rot1 = noise[0] * abs(delta_rot1) + noise[1] * delta_trans
    sigma_delta_trans = noise[2] * delta_trans + noise[3] * (abs(delta_rot1) + abs(delta_rot2))
    sigma_delta_rot2 = noise[0] * abs(delta_rot2) + noise[1] * delta_trans

    for particle in particles:
        new_particle = dict()
        noisy_delta_rot1 = delta_rot1 + np.random.normal(0, sigma_delta_rot1)
        noisy_delta_trans = delta_trans + np.random.normal(0, sigma_delta_trans)
        noisy_delta_rot2 = delta_rot2 + np.random.normal(0, sigma_delta_rot2)
        new_particle['x'] = particle['x'] + noisy_delta_trans * np.cos(particle['theta'] + noisy_delta_rot1)
        new_particle['y'] = particle['y'] + noisy_delta_trans * np.sin(particle['theta'] + noisy_delta_rot1)
        new_particle['theta'] = particle['theta'] + noisy_delta_rot1 + noisy_delta_rot2
        new_particles.append(new_particle)
    return new_particles

def weight_update(sensor_data, particles, landmarks):
    # Computes the observation likelihood of all particles, given the
    # particle and landmark positions and sensor measurements
    # (probabilistic sensor models slide 33)
    #
    # The employed sensor model is range only.

    sigma_r = 0.2

    #measured landmark ids and ranges
    ids = sensor_data['id']
    ranges = sensor_data['range']
    bearings = sensor_data['bearing']  # not using this information

    weights = []

    for particle in particles:
        all_meas_likelihood = 1.0 
            # loop for each observed landmark
        for i in range(len(ids)):
            lm_id = ids[i]
            meas_range = ranges[i]
            bearing = bearings[i]  # not using this info
            lx = landmarks[lm_id][0]
            ly = landmarks[lm_id][1]
            px = particle['x']
            py = particle['y']
            meas_range_exp = np.sqrt((lx - px) ** 2 + (ly - py) ** 2)
            meas_likelihood = scipy.stats.norm.pdf(meas_range, meas_range_exp, sigma_r)
            all_meas_likelihood = all_meas_likelihood * meas_likelihood
        weights.append(all_meas_likelihood)
    return weights

def resample_particles(particles, weights):
    # Returns a new set of particles obtained by performing
    # stochastic universal sampling, according to the particle weights.

    new_particles = []

    # normalize weights
    normalizer = sum(weights)
    if normalizer < 0.01:
        new_particles = generate_particles(len(weights), [-1, 12, 0, 10])
        return new_particles
    weights = weights / normalizer
    step = 1.0 / len(particles)
    u = np.random.uniform(0, step)
    c = weights[0]
    i = 0
    new_particles = []
    for particle in particles:
        while u > c:
            i = i + 1
            c = c + weights[i]
        # add that particle
        new_particles.append(particles[i])

        # increase the threshold
        u = u + step
    return new_particles



def main():
    # implementation of a particle filter for robot pose estimation

    print("Reading landmark positions")
    landmarks = read_world_map("./data/world_map.dat")

    print("Reading sensor data")
    sensor_readings = read_sensor_measurement("./data/sensor_measurement.dat")

    #initialize the particles
    map_limits = [-1, 12, 0, 10]
    particles = generate_particles(50, map_limits)
    filenames = []


    #run particle filter
    for timestep in range(int(len(sensor_readings))):
        filename = f'fig_{timestep}.png'
        filenames.append(filename)
        #plot the current state
        plot(particles, landmarks, map_limits, filename)
        plt.show()
        plt.pause(0.2)
        # plt.close()

        #predict particles by sampling from motion model with odometry info
        new_particles = sample_motion(sensor_readings[timestep, 'odometry'], particles)

        #calculate importance weights according to sensor model
        weights = weight_update(sensor_readings[timestep, 'sensor'], new_particles, landmarks)

        #resample new particle set according to their importance weights
        particles = resample_particles(new_particles, weights)

    # build gif
    with imageio.get_writer('mygif.gif', mode='I', duration=0.2) as writer:
        for filename in filenames:
            image = imageio.imread(filename)
            writer.append_data(image)


    # Remove files
    for filename in set(filenames):
        os.remove(filename)


if __name__ == "__main__":
    main()