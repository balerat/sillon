import numpy as np
import numba

@numba.njit(fastmath=True, parallel=True)
def qc_potential(x_list, y_list, k_lattice, phi_x, phi_y, phi_t, phi_d, theta=0):
    '''
    Function to calculate a potential in rotated coordinate and with a shifted coordinate
    '''
    x_shifted = x_list
    y_shifted = y_list

    x_rotated = x_shifted * np.cos(theta) - y_shifted * np.sin(theta)
    y_rotated = x_shifted * np.sin(theta) + y_shifted * np.cos(theta)

    V_x = np.sin(k_lattice * (x_rotated) + phi_x)**2
    V_y = np.sin(k_lattice * (y_rotated) + phi_y)**2
    V_t = np.sin(k_lattice * (x_rotated + y_rotated) / np.sqrt(2) + phi_t)**2
    V_d = np.sin(k_lattice * (x_rotated - y_rotated) / np.sqrt(2) + phi_d)**2

    return V_x + V_y + V_t + V_d

def generate_xy_list(img):
    x_list = np.arange(img.shape[1]) - img.shape[1] * 0.5
    y_list = np.arange(img.shape[0]) - img.shape[0] * 0.5
    x_list, y_list = np.meshgrid(x_list, y_list)
    return x_list, y_list

@numba.njit(fastmath=True, parallel=True)
def generate_xy_list_scaled(img, scaling=10):
    x_list = np.arange(img.shape[1]) - img.shape[1] * 0.5
    y_list = np.arange(img.shape[0]) - img.shape[0] * 0.5
    x_list = np.linspace(x_list.min(), x_list.max(), len(x_list) * scaling)
    y_list = np.linspace(y_list.min(), y_list.max(), len(y_list) * scaling)
    dx=np.diff(x_list).mean()
    dy=np.diff(y_list).mean()
    x_list, y_list = np.meshgrid(x_list, y_list)
    return x_list, y_list, dx, dy

@numba.njit(fastmath=True, parallel=True)
def rotate(x, y, theta):
    xx = x
    x = x * np.cos(theta) - y * np.sin(theta)
    y = xx * np.sin(theta) + y * np.cos(theta)
    return x, y


def apply_mask(img, x_list, y_list):
    mask = img > 0
    x_list_masked = x_list[mask]
    y_list_masked = y_list[mask]
    img = img[mask].ravel()
    return img, x_list_masked, y_list_masked

def preprocessing(img, cutoff, median, scale, gamma=0):
    img = np.where(img <= cutoff, 0, img)

    if scale != 0:
        img = np.log1p(img * scale) / np.log1p(scale)

    if gamma !=0:
        img = (img + 10) ** gamma
    return img

def power_law_scaling(img, scale, gamma):
    return (img * scale) ** gamma

def gaussian(r, amplitude, sigma_r, offset):
    return amplitude * np.exp(-0.5*(r)**2/sigma_r**2) / (sigma_r * np.sqrt(2 * np.pi)) + offset