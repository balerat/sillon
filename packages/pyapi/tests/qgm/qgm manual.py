import os
import argparse
import tomllib
import tomli_w
import cProfile
import pickle
import numpy as np
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from qgm.misc import preprocessing
from qgm.fitting import fit_data
from qgm.octogon import populate, populate_pixelwise, calc_octagon_rms_bingaussian
from plots.result import *
import simplypy as sp
from simplycommon import database as scdb
import pytest

@pytest.fixture
def env():
    return

def test_qgm
print('Import done')
sp.track()
print('ps.track() done')
parser = argparse.ArgumentParser(description="Add the parameter as a toml file.")
parser.add_argument("config", help="Path to the TOML configuration file")
args = parser.parse_args()
with open(args.config, "rb") as f:
    parameters = tomllib.load(f)


test_engine = scdb.create_engine("sqlite:///.simply/database.sql")

##################################
##         Parameters           ##
##################################

sp.addParams("test_param", 0)
assert scdb.load_param(engine) != None
assert scdb.load_param(engine)[0] == {'test_param': 0}


data_dir = parameters['Environment']['data_dir']
res_dir_name = parameters['Environment']['result_dir']
res_dir = Path(data_dir) / 'qgm_fitting_res' / res_dir_name / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
os.makedirs(res_dir, exist_ok=True)
seed = parameters['Environment']['seed']
rois = {'bg': tuple(parameters['Data']['roi_bg']), 'main': tuple(parameters['Data']['roi_main'])}
n_shots, n_runs = parameters['Data']['n_shots'], parameters['Data']['n_runs']
n_hist = parameters['Data']['n_hist']
filter_in = parameters['Data']['filter_in']
filter_post = parameters['Data']['filter_post']
n_row, n_col = n_shots, n_runs

bound_k0 = parameters['Fitting']['bound_k0']
bound_phi = (-np.pi/2, np.pi/2)
bound_theta = parameters['Fitting']['bound_theta']
n_bins_rms = parameters['Fitting']['n_bins_rms']
fit_population = parameters['Fitting']['fit_population']
mode = parameters['Fitting']['mode']
bounds = [bound_k0, bound_phi, bound_theta]
lamb = parameters['Fitting']['lamb']

verbose = parameters['Debug']['verbose']
profiling = parameters['Debug']['profiling']

sp.addParams("bounds", bounds)
assert scdb.load_param(engine)[0]['bounds'] != None

##################################
##           Loading            ##
##################################

imgs, imgs_param = loadData(folders=[data_dir], variables=['lattice_depth', 'timestamp'], rois=rois, NCol=n_col, NRow=n_row)
lattice_depths = np.array(imgs_param['lattice_depth'])
oct_rms= np.zeros(len(imgs))
fitting_parameters, rms_fit_param, pops, mins, oct_mins, r_hist, pop_hist= (np.zeros((len(imgs)), dtype=object) for _ in range(7))
r_bin_centres,  hist,  = [],  np.zeros((len(imgs), n_hist))


##################################
##           Fitting            ##
##################################

if profiling:
    profiler = cProfile.Profile()
    profiler.enable()

print('Computation start.')

for i in tqdm(range(len(imgs))):
    if verbose:
        print('Processing image {}/{}'.format(i+1, len(imgs)))
        print('lattice depth: {:.1f} Er'.format(lattice_depths[i]))

    fitting_parameters[i] = fit_data(imgs[i], bounds, [filter_in], fit_population=fit_population, mode=mode, verbose=verbose, lamb=lamb, seed=seed)
    if verbose:
        print('params: {}'.format(fitting_parameters[i]))

    if parameters['Switch']['population_mode'] == 'pixelwise':
        pops[i], mins[i], oct_mins[i] = populate_pixelwise(imgs[i], params=fitting_parameters[i], verbose=verbose, **parameters['Octagon'])
    else:
        pops[i], mins[i], oct_mins[i] = populate(preprocessing(imgs[i], *filter_post), params=fitting_parameters[i], verbose=verbose, **parameters['Octagon'])
    if verbose:
        print('first pops: {}'.format(pops[i][0]))
        print('len mins: {}'.format(len(mins)))
        print('len oct_mins: {}'.format(len(oct_mins[i][0])))

    oct_rms[i],omega_r, rms_fit_param[i], r_hist[i], pop_hist[i] = calc_octagon_rms_bingaussian(oct_mins[i], pops[i])
    if verbose:
        print('RMS_gauss: {:.3f}'.format(oct_rms[i]))

    hist[i], r_bins = np.histogram(omega_r, bins=n_hist, density=True, weights=pops[i]) #, range=(0, np.pi/2**0.5)ç
    r_bin_centres = 0.5 * (r_bins[:-1]+r_bins[1:])

hist = hist.reshape((n_row, n_col, n_hist))
hist = hist.sum(axis=0)
oct_rms = oct_rms.reshape(n_row, n_col)
r_hist = r_hist.reshape(n_row, n_col)
pop_hist = pop_hist.reshape(n_row, n_col)

print('Computation done.')

##################################
##             OUT              ##
##################################

if profiling:
    profiler.disable()
    profiler.dump_stats(res_dir / 'profiling.txt')
    profiler.print_stats()

with open(res_dir / "config.toml", "wb") as f:
    tomli_w.dump(parameters, f)

out = {
        'oct_rms': oct_rms,
        'fitting_parameter':fitting_parameters,
        'pops': pops,
        'mins': mins,
        'rms_fit_param': rms_fit_param
    }

with open(res_dir / "out.pkl", "wb") as f:
    pickle.dump(out, f)

sp.addResult('result', str(res_dir / "out.pkl"))
assert Path("res_dir/").exist_ok == True

##################################
##          Plotting            ##
##################################

print('Generating plots')

plot_allfit(n_col, n_row, imgs, fitting_parameters, lattice_depths, res_dir)
plot_dens_vs_radius(n_col, r_bin_centres, lattice_depths, hist, res_dir)
plot_rms_gauss_vs_depth(lattice_depths, oct_rms, n_shots, n_col, res_dir)
plot_rms_std_vs_depth(lattice_depths, oct_rms, n_shots, n_col, res_dir)

print('QGM job done.')

