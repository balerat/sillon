import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from qgm.misc import generate_xy_list, qc_potential

cmap = LinearSegmentedColormap.from_list('TestCmap', [(0, (1., 0, 0, 0.0)), (1, (0.5, 0., 0., 1.))])

# Figure 1: Plot all fits with original data
def plot_allfit(n_col, n_row, imgs, params_list, lattice_depths, res_dir):
    fig = plt.figure(figsize=(5 * n_col,5 * n_row), dpi=100)
    fig.tight_layout()
    for i in range(len(imgs)):
        ax=fig.add_subplot(n_row, n_col, i+1)
        x_list, y_list = generate_xy_list(imgs[i])
        potential = qc_potential(x_list, y_list, *params_list[i])
        ax.imshow(potential, cmap='Blues_r', extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), origin='lower')
        ax.imshow(imgs[i], vmin=0, vmax=0.5, cmap=cmap, extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), origin='lower')
        ax.set_title('{:.1f}$E_r$'.format(lattice_depths[i]))
        ax.set_xlabel('x')
        ax.set_ylabel('y')
    plt.savefig(res_dir / 'all_fits.png')
    return

# Figure 2: Population density vs. Octagon radius
def plot_dens_vs_radius(n_col, r_bin_centres, lattice_depths, hist, res_dir):
    plt.figure(figsize=(10, 5))
    for i in range(n_col):
        mask = np.where(hist[i] > 0.1)
        label = '{:.1f}$E_r$'.format(lattice_depths[i]) if i % 4 == 0 else None
        plt.plot(
            r_bin_centres[mask],
            hist[i][mask] / r_bin_centres[mask],
            c=(i * 0.8 / n_col, 0.2, (n_col - i) * 0.8 / n_col),
            label=label,
        )
    plt.yscale('log')
    plt.xlabel('Octagon radius')
    plt.ylabel('Population density (a.u.)')
    plt.legend(fontsize='small')
    plt.title('Population Density vs Octagon Radius')
    plt.savefig(res_dir / 'population_density_vs_radius.png')
    return

# Figure 3: RMS vs. Lattice depth
def plot_rms_vs_depth(lattice_depths, oct_rms, n_shots, n_col, res_dir):
    plt.figure(figsize=(8, 6))
    plt.errorbar(
        lattice_depths[:n_col],
        oct_rms.mean(axis=0),
        yerr=oct_rms.std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        c='k',
    )
    plt.xlabel('Lattice depth $(E_r)$')
    plt.ylabel('Configuration space RMS')
    plt.title('RMS vs Lattice Depth')
    plt.savefig(res_dir / 'rms_vs_lattice_depth.png')
    return

# Figure 3_bis: RMS vs. Lattice depth hist
def plot_rms_hist_vs_depth(lattice_depths, oct_rms_hist, n_shots, n_col, res_dir):
    plt.figure(figsize=(8, 6))
    plt.errorbar(
        lattice_depths[:n_col],
        oct_rms_hist.mean(axis=0),
        yerr=oct_rms_hist.std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        c='k',
    )
    plt.xlabel('Lattice depth $(E_r)$')
    plt.ylabel('Configuration space RMS')
    plt.title('RMS_hist vs Lattice Depth hist')
    plt.savefig(res_dir /'rms_vs_lattice_depth_hist.png')
    return

# Figure 3_bis_bis: RMS vs. Lattice gauss
def plot_rms_gauss_vs_depth(lattice_depths, oct_rms_gauss, n_shots, n_col, res_dir):
    plt.figure(figsize=(8, 6))
    plt.errorbar(
        lattice_depths[:n_col],
        oct_rms_gauss.mean(axis=0),
        yerr=oct_rms_gauss.std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        c='k',
    )
    plt.xlabel('Lattice depth $(E_r)$')
    plt.ylabel('Configuration space RMS')
    plt.title('RMS vs Lattice Depth using guassian')
    plt.savefig(res_dir / 'rms_vs_lattice_depth_gauss.png')
    return

# Figure 4: RMS standard deviation vs. Lattice depth
def plot_rms_std_vs_depth(lattice_depths, oct_rms, n_shots, n_col, res_dir):
    plt.figure(figsize=(8, 6))
    plt.plot(
        lattice_depths[:n_col],
        oct_rms.std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        c='b',
    )
    plt.xlabel('Lattice depth $(E_r)$')
    plt.ylabel('RMS Standard Deviation')
    plt.title('RMS Std Deviation vs Lattice Depth')
    plt.savefig(res_dir / 'rms_std_dev_vs_lattice_depth.png')
    return

# Figure 5: RMS vs Lattice depth from oldest to newest run

def plot_rms__vs_depth_stability(n_row, lattice_depths, oct_rms, n_shots, n_col, res_dir):
    if n_row > 1:
        cmap_fig5 = plt.get_cmap("coolwarm")
        plt.figure(figsize=(8, 6))
        for i in range(n_row):
            color = cmap_fig5(i / (n_row - 1))
            ax = plt.plot(lattice_depths[:n_col], oct_rms[i,:], label=f'Shot number {i}', color=color)
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=0, vmax=n_shots-1))
        sm.set_array([])  
        cbar = plt.colorbar(sm, ax=ax)
        cbar.set_label("n_shots (higher the newer)")  # Label for the colorbar
        plt.xlabel('Lattice depth $(E_r)$')
        plt.ylabel('Configuration space RMS')
        plt.title('RMS vs Lattice Depth for each shot')
        plt.savefig(res_dir /'rms_vs_lattice_depth_eachshot.png')
    return

# Figure 6: Same radius zone in configuration space average population vs lattice depth
def plot_same_radius_vs_depth(n_row, lattice_depths, n_shots, n_col, res_dir, pop_hist, r_hist):
    plt.figure(figsize=(8, 6))
    pop_hist = np.asarray(pop_hist)
    r_hist = np.asarray(r_hist)
    print(pop_hist.shape)
    pop_hist = pop_hist.reshape(n_row, n_col, pop_hist.shape[1])
    # plt.plot(lattice_depths[:n_col], pop_hist[:,0], label=f'{r_hist[0,0]}')
    # plt.plot(lattice_depths[:n_col], pop_hist[:,1], label=f'{r_hist[0,1]}')
    # plt.plot(lattice_depths[:n_col], pop_hist[:,-2], label=f'{r_hist[0,-2]}')
    # plt.plot(lattice_depths[:n_col], pop_hist[:,-1], label=f'{r_hist[0,-1]}')
    plt.errorbar(
        lattice_depths[:n_col],
        pop_hist[:,:,0].mean(axis=0),
        yerr=pop_hist[:,:,0].std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        label=f'{np.round(r_hist[0,0], 2)}'
    )
    plt.errorbar(
        lattice_depths[:n_col],
        pop_hist[:,:,1].mean(axis=0),
        yerr=pop_hist[:,:,1].std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        label=f'{np.round(r_hist[0,1], 2)}'
    )
    plt.errorbar(
        lattice_depths[:n_col],
        pop_hist[:,:,-2].mean(axis=0),
        yerr=pop_hist[:,:,-2].std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        label=f'{np.round(r_hist[0,-2], 2)}'
    )
    plt.errorbar(
        lattice_depths[:n_col],
        pop_hist[:,:,-1].mean(axis=0),
        yerr=pop_hist[:,:,-1].std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        label=f'{np.round(r_hist[0,-1], 2)}'
    )
    plt.legend()
    plt.xlabel('Lattice depth $(E_r)$')
    plt.ylabel('OD')
    plt.title('Same radius zone in configuration space average population vs lattice depth')
    plt.savefig(res_dir / 'conf_pop2.png')
    return

# Figure 7: OD sum vs. Lattice depth
def plot_OD_vs_depth(n_row, lattice_depths, n_shots, n_col, res_dir, imgs, r_hist):
    OD_list = [imgs[i].sum() for i in range(len(imgs))]
    OD_list = np.array(OD_list).reshape(n_row, n_col)
    plt.figure(figsize=(8, 6))
    plt.errorbar(
        lattice_depths[:n_col],
        OD_list.sum(axis=0),
        yerr=OD_list.std(axis=0) / n_shots**0.5,
        marker='o',
        mec='k',
        mfc='w',
        label=f'{np.round(r_hist[0][0], 2)}'
    )
    plt.xlabel('Lattice depth $(E_r)$')
    plt.ylabel('OD sum')
    plt.ylim(0, np.max(OD_list.sum(axis=0)))
    plt.title('OD sum vs Lattice Depth')
    plt.savefig(res_dir/ 'OD.png')
    return