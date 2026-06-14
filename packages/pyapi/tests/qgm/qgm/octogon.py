import numpy as np
import numba
from scipy import ndimage
import matplotlib.pyplot as plt
from scipy.spatial import KDTree
from scipy.optimize import curve_fit
from pprint import pprint
from .misc import generate_xy_list, rotate
import qgm.fitting
from plots.verbose_octagon import *

@numba.njit(fastmath=True, parallel=True)
def get_octagon_pos(x, y, k_lattice, phi_arr):
    '''
    Transform real space minmum coordinates to octogon coordinates.
    '''
    theta_1 = k_lattice * x + phi_arr[0]
    theta_2 = k_lattice * y + phi_arr[1]
    theta_3 = k_lattice * (x + y) / np.sqrt(2) + phi_arr[2]
    theta_4 = k_lattice * (x - y) / np.sqrt(2) + phi_arr[3]
    
    theta_1 = theta_1 - np.pi * np.rint(theta_1 / np.pi)
    theta_2 = theta_2 - np.pi * np.rint(theta_2 / np.pi)
    theta_3 = theta_3 - np.pi * np.rint(theta_3 / np.pi)
    theta_4 = theta_4 - np.pi * np.rint(theta_4 / np.pi)
    
    theta_x = theta_1 - (theta_3 + theta_4) / np.sqrt(2)
    theta_y = theta_2 - (theta_3 - theta_4) / np.sqrt(2)
    
    return theta_x, theta_y

def find_qc_minimum(img, params, size, center, cloud_size, background_center, cloud_size_background, verbose=False):
    '''
    Find the minimum of the quasicrystal potential with ndimage.minimum_filter, get its coordinates on the octogon
    and verifies that it lies within its bounds.
    '''
    k_lattice, theta = params[0], params[-1]
    phi_arr = params[1:len(params)-1] # -1 ?
    x_list, y_list = generate_xy_list(img)
    potential = qgm.fitting.qc_potential(x_list, y_list, *params)

    # Find all minimum in the Qc
    minimums = ndimage.minimum_filter(potential, size=size, mode='constant', cval=0.0) == potential
    x_min, y_min = x_list[np.where(minimums)], y_list[np.where(minimums)]

    # Find all minimums in the cloud for background and the image
    points = np.column_stack((x_min.ravel(), y_min.ravel()))
    tree = KDTree(points)
    indices_cloud_upper = tree.query_ball_point([x_list[center], y_list[center]], r=cloud_size[1])
    indices_cloud_lower = tree.query_ball_point([x_list[center], y_list[center]], r=cloud_size[0])
    indices_cloud = [item for item in indices_cloud_upper if item not in indices_cloud_lower]
    indices_background = tree.query_ball_point([x_list[background_center], y_list[background_center]], r=cloud_size_background)
    x_min = points[indices_cloud,0]
    y_min = points[indices_cloud,1]
    x_min_background = points[indices_background, 0]
    y_min_background = points[indices_background, 1]

    # Rotate all the points and get their coordinates in configuration space
    rot_x_min, rot_y_min = rotate(x_min, y_min, theta)
    rot_x_min_background, rot_y_min_background = rotate(x_min_background, y_min_background, theta)
    omega_x, omega_y = get_octagon_pos(rot_x_min, rot_y_min, k_lattice, phi_arr)
    omega_x_background, omega_y_background = get_octagon_pos(rot_x_min_background, rot_y_min_background, k_lattice, phi_arr)


    if verbose:
        pprint('Len minimums: {}'.format(len(x_min)))
        plot_qc_min_verbose(x_list, y_list, params, center, x_min, y_min, omega_x, omega_y)

    return [x_min, y_min], [omega_x, omega_y], [x_min_background, y_min_background], [omega_x_background, omega_y_background]

def populate(img, params, pixel_width=9, search_size=8, cloud_center=(250, 250), cloud_size=[0, 400], background_center=(70, 70), cloud_size_background=70, population_cutoff=0.1, verbose=False):
    '''
    Checks the population of each point in the octogon and filters out the ones with a population below pop_cutoff.
    '''
    background_center = tuple(background_center)
    cloud_size = tuple(cloud_size)
    cloud_center = tuple(cloud_center)
    mins, oct_coord, mins_background, oct_coord_background = find_qc_minimum(img, params, size=search_size, center=cloud_center, cloud_size=cloud_size, background_center=background_center, cloud_size_background=cloud_size_background, verbose=verbose)
    x_list, y_list = generate_xy_list(img)
    omega_x, omega_y = oct_coord[0], oct_coord[1]
    x_min, y_min = mins[0], mins[1]
    x_min_background, y_min_background = mins_background[0], mins_background[1]
    omega_x_background, omega_y_background = oct_coord_background[0], oct_coord_background[1]

    # Create the tree for the entire image
    points = np.column_stack((x_list.ravel(), y_list.ravel()))
    tree = KDTree(points)
    populations, populations_background  = np.zeros(len(x_min)), np.zeros(len(x_min_background))

    for i in range(len(x_min_background)):
        indices_background = tree.query_ball_point([x_min_background[i], y_min_background[i]], r=pixel_width)
        if indices_background:  
            populations_background[i] = img.ravel()[indices_background].sum()
    
    for i in range(len(x_min)):
        indices = tree.query_ball_point([x_min[i], y_min[i]], r=pixel_width)
        if indices:  
            populations[i] = img.ravel()[indices].sum()
    
    # The cutoff
    if population_cutoff != 0:
        populations[np.where(populations <= population_cutoff)] = 0
        
    if verbose:
        plot_populate_verbose(omega_x, omega_y, populations, omega_x_background, omega_y_background, populations_background, params, 
                          x_min, y_min, cloud_center, img, background_center, x_min_background, y_min_background)
       

    return populations, mins, oct_coord

def calc_octagon_rms_bingaussian(oct_mins, pops, n_bins=30, verbose=False):
    if n_bins < 2:
        print('bins too small')
        return
    omega_r = np.sqrt((oct_mins[0]**2 + oct_mins[1]**2))
    pops_hist = np.histogram(omega_r, bins=n_bins, weights=pops)[0] #/ np.histogram(omega_r, bins=n_bins)[0]
    spacing = np.histogram(omega_r, bins=n_bins)[1][1] - np.histogram(omega_r, bins=n_bins)[1][0]
    r_histo = np.array([np.histogram(omega_r, bins=n_bins)[1][i] + spacing/2 for i in range(n_bins)])
    for i in range(len(pops_hist)):
        pops_hist[i] = pops_hist[i] / np.pi / ((r_histo[i] + spacing)**2 - (r_histo[i] - spacing)**2)
    pops_hist = pops_hist / pops_hist.max()
    try:
        gaussian_params = curve_fit(gaussian, r_histo, pops_hist, maxfev=4000, p0=[1,0.7,0])
    except:
        print('Failed gauss fit')
        gaussian_params = [[0,0]]
    return np.abs(gaussian_params[0][1]), omega_r, gaussian_params, r_histo, pops_hist

def populate_pixelwise(img, params, pixel_width=9, search_size=8, cloud_center=(250, 250), cloud_size=[0, 400], background_center=(70, 70), cloud_size_background=70, population_cutoff=0.1, verbose=False):
    '''
    Checks the population of each point in the octogon and filters out the ones with a population below pop_cutoff.
    '''
    cloud_size = tuple(cloud_size)
    cloud_center = tuple(cloud_center)
    x_list, y_list = generate_xy_list(img)
    # Find all minimums in the cloud for background and the image
    points = np.column_stack((x_list.ravel(), y_list.ravel()))
    tree = KDTree(points)
    indices_cloud_upper = tree.query_ball_point([x_list[cloud_center], y_list[cloud_center]], r=cloud_size[1])
    indices_cloud_lower = tree.query_ball_point([x_list[cloud_center], y_list[cloud_center]], r=cloud_size[0])
    indices_cloud = [item for item in indices_cloud_upper if item not in indices_cloud_lower]
    x_list = x_list.ravel()[indices_cloud]
    y_list = y_list.ravel()[indices_cloud]
    theta = params[-1]
    k_lattice = params[0]
    phi_arr = params[1:-1]
    rot_x, rot_y = rotate(x_list, y_list, theta)
    omega_x, omega_y = get_octagon_pos(rot_x, rot_y, k_lattice, phi_arr)
    mins = [x_list, y_list]
    populations = np.zeros(len(x_list))
    for i in range(len(indices_cloud)):
        populations[i] = img.ravel()[indices_cloud[i]]
    omega = np.vstack((omega_x, omega_y)).T
    rounded = np.round(omega, decimals=9) 
    unique_coords, inverse = np.unique(rounded, axis=0, return_inverse=True)
    summed_populations = np.bincount(inverse, weights=populations)
    unique_omega_x = unique_coords[:, 0]
    unique_omega_y = unique_coords[:, 1]
    if verbose:
        plot_populate_pixelwise_verbose(omega_x, omega_y, populations, params, 
                          mins[0], mins[1], cloud_center, img)
    return summed_populations, mins, [unique_omega_x, unique_omega_y]