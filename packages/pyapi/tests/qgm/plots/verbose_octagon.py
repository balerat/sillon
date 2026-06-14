import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.pyplot as plt
from qgm.misc import qc_potential, generate_xy_list, gaussian

cmap_red = LinearSegmentedColormap.from_list('TestCmap', [(0, (1., 0, 0, 0.0)), (1, (1, 0, 0., 1.))])

# Fig 1: Radius in octogon for all min point in the selected cloud
def plot_qc_min_verbose(x_list, y_list, params, center, x_min, y_min, omega_x, omega_y):
    fig_1, ax = plt.subplots(1, 1, figsize=(10, 10), dpi= 100)
    potential = qc_potential(x_list, y_list, *params)
    ax.imshow(np.flipud(potential), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    im = plt.scatter(x_min, y_min, c=np.sqrt(omega_x**2 + omega_y**2), s=5, cmap='inferno')
    ax.scatter(x_list[center], y_list[center], c='red', s=10)
    ax.set_title('Minimum and their radius from the center of the octogon of the fittend Qc')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    fig_1.colorbar(im, ax=ax)
    plt.show()

    return

def plot_populate_pixelwise_verbose(omega_x, omega_y, populations, params, x_min, y_min, center, img):
# FIG1: The octogon
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.scatter(omega_x, omega_y, c=populations, s=1, cmap=cmap_red, edgecolors=(0,0,0,0))
    ax.set_title('Configuration space position of each minimum in the cloud')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    plt.show()

# FIG 3: Ditribution of cloud of the point
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.plot((omega_x**2 + omega_y**2)**0.5, populations, 'ko', mfc='w')
    ax.set_title('Distribution of minimums OD vs their radius in the octogon in the cloud')
    ax.set_ylabel('OD (avg)')
    ax.set_xlabel('r')
    plt.show()


# FIG 5: Population of each minimums in the selected cloud
    x_list, y_list = generate_xy_list(img)
    potential = qc_potential(x_list, y_list, *params)
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(np.flipud(potential), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    im = plt.scatter(x_min, y_min, c=populations, s=50, cmap='inferno')
    ax.set_title('OD of minimum in the cloud')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    ax.set_xlim(-100, 100)
    ax.set_ylim(-100, 100)
    _.colorbar(im, ax=ax)
    plt.show()


# FIG 6: Population of each minimums in the selected cloud
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    # ax.imshow(np.flipud(potential), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    ax.imshow(np.flipud(img), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), vmin=0, vmax=0.5, cmap=cmap_red)
    ax.scatter(x_list[center], y_list[center], c='green', s=50)
    im = plt.scatter(x_min, y_min, c=populations, s=10, cmap='inferno')
    ax.set_title('OD of minimum in the cloud')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    _.colorbar(im, ax=ax)
    plt.show()

    return

def plot_rms_verbose(oct_mins, pops, gaussian_params):
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.plot((oct_mins[0]**2 + oct_mins[1]**2)**0.5, pops, 'ko', mfc='w')
    ax.plot(np.linspace(0,1.75, 100), gaussian(np.linspace(0,1.75, 100), *gaussian_params[0]))
    ax.legend()
    ax.set_title('Distribution of minimums OD vs their radius in the octogon in the background')
    ax.set_ylabel('OD (avg)')
    ax.set_xlabel('r')
    plt.show()
    return

def plot_populate_verbose(omega_x, omega_y, populations, omega_x_background, omega_y_background, populations_background, params, x_min, y_min, center, img, background, x_min_background, y_min_background):
# FIG1: The octogon
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.scatter(omega_x, omega_y, c=populations, s=1, cmap=cmap_red, edgecolors=(0,0,0,0))
    ax.set_title('Configuration space position of each minimum in the cloud')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    plt.show()


# FIG 2: Ditribution of background and cloud of the point
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.plot((omega_x**2 + omega_y**2)**0.5, populations, 'ko', mfc='w')
    ax.plot((omega_x_background**2 + omega_y_background**2)**0.5, populations_background, 'ko', mfc='w', c='red')
    ax.set_title('Distribution of minimums OD vs their radius in the octogon in the cloud (black) and in the background (red)')
    ax.set_ylabel('OD (avg)')
    ax.set_xlabel('r')
    plt.show()


# FIG 3: Ditribution of cloud of the point
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.plot((omega_x**2 + omega_y**2)**0.5, populations, 'ko', mfc='w')
    ax.set_title('Distribution of minimums OD vs their radius in the octogon in the cloud')
    ax.set_ylabel('OD (avg)')
    ax.set_xlabel('r')
    plt.show()


# FIG 4: Ditribution of background of the point
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.plot((omega_x_background**2 + omega_y_background**2)**0.5, populations_background, 'ko', mfc='w')
    ax.set_title('Distribution of minimums OD vs their radius in the octogon in the background')
    ax.set_ylabel('OD (avg)')
    ax.set_xlabel('r')
    plt.show()


# FIG 5: Population of each minimums in the selected cloud
    x_list, y_list = generate_xy_list(img)
    potential = qc_potential(x_list, y_list, *params)
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(np.flipud(potential), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    im = plt.scatter(x_min, y_min, c=populations, s=50, cmap='inferno')
    ax.set_title('OD of minimum in the cloud')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    ax.set_xlim(-100, 100)
    ax.set_ylim(-100, 100)
    _.colorbar(im, ax=ax)
    plt.show()


# FIG 6: Population of each minimums in the selected cloud
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    # ax.imshow(np.flipud(potential), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    ax.imshow(np.flipud(img), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), vmin=0, vmax=0.5, cmap=cmap_red)
    ax.scatter(x_list[center], y_list[center], c='green', s=50)
    im = plt.scatter(x_min, y_min, c=populations, s=10, cmap='inferno')
    ax.set_title('OD of minimum in the cloud')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    _.colorbar(im, ax=ax)
    plt.show()


# FIG 7: Population of each minimums in the selected background
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(np.flipud(img), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), vmin=0, vmax=0.5, cmap=cmap_red)
    ax.scatter(x_list[background], y_list[background], c='purple', s=50)
    im = plt.scatter(x_min_background, y_min_background, c=populations_background, s=10, cmap='inferno')
    ax.set_title('OD of minimum in the background')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    _.colorbar(im, ax=ax)
    plt.show()



# FIG 8: Histogram for OD (avg) and radius of cloud vs background
    r_cloud = np.sqrt(omega_x**2 + omega_y**2)
    r_background = np.sqrt(omega_x_background**2 + omega_y_background**2)

    plt.figure(figsize=(10, 10))
    plt.hist(r_cloud, bins=30, alpha=0.5, color='black', label='Cloud', edgecolor='black')
    plt.hist(r_background, bins=30, alpha=0.5, color='red', label='Background', edgecolor='red')
    plt.title('Histogram of radius in the octogon for atom cloud and background of the img')
    plt.xlabel('r')
    plt.ylabel('Frequency')
    plt.legend()

    plt.figure(figsize=(10, 10))
    plt.hist(populations, bins=30, alpha=0.5, color='black', label='Cloud', edgecolor='black')
    plt.hist(populations_background, bins=30, alpha=0.5, color='red', label='Background', edgecolor='red')
    plt.title('Histogram of OD (avg) for atom cloud and background of the img')
    plt.xlabel('OD (avg)')
    plt.ylabel('Frequency')
    plt.legend()
    plt.show()

    return