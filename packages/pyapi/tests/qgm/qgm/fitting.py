import numba
import qgm.octogon
import numpy as np
from pprint import pprint
from scipy.optimize import differential_evolution
from .misc import generate_xy_list, apply_mask, rotate, preprocessing, qc_potential
from plots.verbose_fitting import *

@numba.njit(fastmath=True)
def cost_function(params, x_list_masked, y_list_masked, img_ravel, mode, lamb=0): 
    if mode == 'min_outside_oct':
        x_list_rot, y_list_rot = rotate(x_list_masked, y_list_masked, params[-1])
        oct_pos_x, oct_pos_y = qgm.octogon.get_octagon_pos(x_list_rot, y_list_rot, params[0], [params[1], params[2], params[3], params[4]])    
        mask=np.zeros(oct_pos_x.shape)
        mask[np.where(np.abs(oct_pos_x)>np.pi*0.5)]=1
        mask[np.where(np.abs(oct_pos_y)>np.pi*0.5)]=1
        mask[np.where(np.abs(oct_pos_x + oct_pos_y) / 2 ** 0.5 > np.pi * 0.5)] = 1
        mask[np.where(np.abs(oct_pos_x - oct_pos_y) / 2 ** 0.5 > np.pi * 0.5)] = 1
        cost = np.sum(img_ravel * mask) #+  lamb * np.sum(img_ravel * mask)
        return cost
    elif mode == 'min_energy':
        return np.sum(img_ravel * qc_potential(x_list_masked, y_list_masked, params[0], params[1], params[2], params[3], params[4], params[5]))
    elif mode == 'combined':
        x_list_rot, y_list_rot = rotate(x_list_masked, y_list_masked, params[-1])
        oct_pos_x, oct_pos_y = qgm.octogon.get_octagon_pos(x_list_rot, y_list_rot, params[0], [params[1], params[2], params[3], params[4]])    
        mask=np.zeros(oct_pos_x.shape)
        mask[np.where(np.abs(oct_pos_x)>np.pi*0.5)]=1
        mask[np.where(np.abs(oct_pos_y)>np.pi*0.5)]=1
        mask[np.where(np.abs(oct_pos_x + oct_pos_y) / 2 ** 0.5 > np.pi * 0.5)] = 1
        mask[np.where(np.abs(oct_pos_x - oct_pos_y) / 2 ** 0.5 > np.pi * 0.5)] = 1
        cost = np.sum(img_ravel * mask) + lamb* np.sum(img_ravel * qc_potential(x_list_masked, y_list_masked, params[0], params[1], params[2], params[3], params[4], params[5])) #+  lamb * np.sum(img_ravel * mask)
        return cost

def optimizer(img, bounds, fit_population=100, mode='min_outside_oct', verbose=False, img_verbose=[], lamb=0, seed=42):
    '''
    This function is the optimizer that will fit the potential to the img. It uses the differential evolution algorithm.
    '''
    k_bounds, phi_bounds, bounds_theta = bounds
    bounds_2fit = [k_bounds, phi_bounds, phi_bounds, phi_bounds, phi_bounds, bounds_theta]
    x_list, y_list = generate_xy_list(img)
    img_ravel, x_list_masked, y_list_masked = apply_mask(img, x_list, y_list)

    result = differential_evolution(cost_function, bounds_2fit, popsize=fit_population, seed=seed, args=(x_list_masked, y_list_masked, img_ravel, mode, lamb))

    if verbose:
        potential = qc_potential(x_list, y_list, *result['x'])
        pprint(result)
        plot_verbose(potential, x_list, y_list, img, img_verbose)

    return result

def fit_data(img, bounds, filters, num_filter=0, fit_population=100, mode='min_outside_oct', verbose=False, lamb=0, seed=42):
    '''
    This function is first called before the optimizer to apply different filter to the img before optimizing it.
    '''
    img_verbose = img
    img = np.where(img <= 0, 0, img)
    img_filtered = preprocessing(img, *filters[num_filter])
    if not(img_filtered > 0).any():
        img_filtered = img

    result = optimizer(img_filtered, bounds, fit_population, mode, verbose, img_verbose,lamb=lamb, seed=seed)

    return result.x