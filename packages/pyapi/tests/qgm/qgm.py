import os
import tomllib
from numba.cuda.compiler import CUDACompileResult
import tomli_w
from lib.AnalysisBase import loadData
import pickle
from sqlmodel import create_engine
import numpy as np
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from qgm.misc import preprocessing
import subprocess
from qgm.fitting import fit_data
import time
from qgm.octogon import populate, populate_pixelwise, calc_octagon_rms_bingaussian
from plots.result import *
import simplypy as sp
from simplypy.api import force_dump, set_context
from simplycommon.database import select_param, select_all, select_uuids
import pytest
import shutil
import atexit

CURRENT_PATH = Path(__file__).parent.resolve()
TEST_DIR = Path(__file__).parent.resolve()
SIMPLY_PATH = TEST_DIR / Path(".simply/")
DB_PATH = SIMPLY_PATH / Path("database.sql")
ARTIFACT_PATH = CURRENT_PATH / Path(".simply/artifact/")
DATA_PATH = TEST_DIR / Path("data")

@pytest.fixture
def env():
    set_context(None)
    if SIMPLY_PATH.exists():
        shutil.rmtree(SIMPLY_PATH)

    print("\n[SETUP] Starting server...")
    server_process = subprocess.Popen(["simply-server-daemon"])
    time.sleep(2)  # Boot up time
    yield

    server_process.terminate()
    server_process.wait()
    set_context(None) # GUARANTEE the next test starts fresh
    if SIMPLY_PATH.exists():
        shutil.rmtree(SIMPLY_PATH)
    set_context(None) # <--- THE MAGIC BULLET

def test_qgm_fast(env):
    print("DBPATH:", DB_PATH)

    sp.init(project_path=CURRENT_PATH)
    print('ps.track() done')

    ### IN THE FUTURE WE WILL NEED TO TAKE INTO ACCOUNT IN SIMPLY THE PARSED ARGUMENTS
    # parser = argparse.ArgumentParser(description="Add the parameter as a toml file.")
    # parser.add_argument("config", help="Path to the TOML configuration file")
    # args = parser.parse_args()
    # with open(args.config, "rb") as f:
    #     parameters = tomllib.load(f)

    with open(TEST_DIR / Path("config.toml"), "rb") as f:
        parameters = tomllib.load(f)

    ##################################
    ##         Parameters           ##
    ##################################

    res_dir_name = parameters['Environment']['result_dir']
    res_dir = DATA_PATH / 'qgm_fitting_res' / res_dir_name / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(res_dir, exist_ok=True)
    seed = parameters['Environment']['seed']
    rois = {'bg': tuple(parameters['Data']['roi_bg']), 'main': tuple(parameters['Data']['roi_main'])}
    n_shots, n_runs = 1, 1 #parameters['Data']['n_shots'], parameters['Data']['n_runs']
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

    sp.log_param("bounds", bounds)

    ##################################
    ##           Loading            ##
    ##################################

    imgs, imgs_param = loadData(folders=[DATA_PATH], variables=['lattice_depth', 'timestamp'], rois=rois, NCol=n_col, NRow=n_row)
    lattice_depths = np.array(imgs_param['lattice_depth'])
    oct_rms= np.zeros(len(imgs))
    fitting_parameters, rms_fit_param, pops, mins, oct_mins, r_hist, pop_hist= (np.zeros((len(imgs)), dtype=object) for _ in range(7))
    r_bin_centres,  hist,  = [],  np.zeros((len(imgs), n_hist))

    ##################################
    ##           Fitting            ##
    ##################################

    print('Computation start.')

    for i in tqdm(range(len(imgs))):
        fitting_parameters[i] = fit_data(imgs[i], bounds, [filter_in], fit_population=fit_population, mode=mode, lamb=lamb, seed=seed)

        if parameters['Switch']['population_mode'] == 'pixelwise':
            pops[i], mins[i], oct_mins[i] = populate_pixelwise(imgs[i], params=fitting_parameters[i], **parameters['Octagon'])
        else:
            pops[i], mins[i], oct_mins[i] = populate(preprocessing(imgs[i], *filter_post), params=fitting_parameters[i], **parameters['Octagon'])

        oct_rms[i],omega_r, rms_fit_param[i], r_hist[i], pop_hist[i] = calc_octagon_rms_bingaussian(oct_mins[i], pops[i])

        hist[i], r_bins = np.histogram(omega_r, bins=n_hist, density=True, weights=pops[i])
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

    sp.log_result('result', path=str(res_dir / "out.pkl"))

    ##################################
    ##          Plotting            ##
    ##################################

    # print('Generating plots')

    # plot_allfit(n_col, n_row, imgs, fitting_parameters, lattice_depths, res_dir)
    # plot_dens_vs_radius(n_col, r_bin_centres, lattice_depths, hist, res_dir)
    # plot_rms_gauss_vs_depth(lattice_depths, oct_rms, n_shots, n_col, res_dir)
    # plot_rms_std_vs_depth(lattice_depths, oct_rms, n_shots, n_col, res_dir)

    print('QGM job done.')

    force_dump()
    time.sleep(1)

    ##################################
    ##          Testing             ##
    ##################################
    atexit._run_exitfuncs() # The loading of the db is done at exit
    assert SIMPLY_PATH.exists()
    engine = create_engine("sqlite:///" + str(DB_PATH))
    print(select_param(engine))
    assert select_param(engine) != []
    print(select_all(engine))
    assert select_all(engine) != []
    print(select_param(engine))
    assert select_param(engine) != []
    print(select_uuids(engine))
    assert next(ARTIFACT_PATH.rglob("out.pkl"), None)
    engine.dispose()




