import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy.fft as fft
from matplotlib.colors import LinearSegmentedColormap

cmap = LinearSegmentedColormap.from_list('TestCmap', [(0, (1., 0, 0, 0.0)), (1, (1, 0, 0., 1.))])

def plot_verbose(potential, x_list, y_list, img, img_verbose):
# FIG 1: Filtered img and fit
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(np.flipud(potential), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    ax.imshow(np.flipud(img), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap=cmap)
    ax.set_title('Img filtered for this fit (red) and fitted potential (blue)')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')

    # FIG 2: Raw img and fit
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    ax.imshow(np.flipud(potential), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    ax.imshow(np.flipud(img_verbose), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), vmin=0, vmax=0.5, cmap=cmap)
    ax.set_title('Raw img (red) and fitted potential (blue)')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')

    # TO DO CHANGE X AND Y CUT
    # x_cut = 400
    # y_cut = 200
    # # FIG 3: Fig to place the cut img and fit
    # _, ax = plt.subplots(1, 1, figsize=(10, 10))
    # ax.imshow(np.flipud(potential), cmap='Blues_r')
    # ax.imshow(np.flipud(img_verbose), vmin=0, vmax=0.5, cmap=cmap)
    # ax.axhline(x_cut, c='green', linestyle='dashed')
    # ax.axvline(y_cut, c='red', linestyle='dashed')
    # ax.set_title('Img (red) and fitted potential (blue) adn two cut along x and y axis')
    # ax.set_xlabel('x (pixels)')
    # ax.set_ylabel('y (pixels)')

    # # FIG 4: Cut along x and y with filtered and raw img
    # _, axs = plt.subplots(2, 2, figsize=(40, 20))
    # x_lim = (100, 200)
    # axs[0, 0].plot((img_verbose[x_cut,:]+np.mean(img_verbose))/np.max(img_verbose), c='red')
    # axs[0, 0].plot((potential[x_cut,:])/4-0.5, c='orange')
    # axs[0, 0].set_title('x_cut on raw')
    # axs[0, 0].set_xlim(x_lim)
    # axs[0, 1].plot((img_verbose[:, y_cut]+np.mean(img_verbose))/np.max(img_verbose), c='red')
    # axs[0, 1].plot((potential[:, y_cut])/4-0.5, c='orange')
    # axs[0, 1].set_title('y_cut on raw')
    # axs[0, 1].set_xlim(x_lim)
    # axs[1, 0].plot((img[x_cut,:]+np.mean(img))/np.max(img), c='red')
    # axs[1, 0].plot((potential[x_cut,:])/4-0.5, c='orange')
    # axs[1, 0].set_title('x_cut on filtered')
    # axs[1, 0].set_xlim(x_lim)
    # axs[1, 1].plot((img[:, y_cut]+np.mean(img))/np.max(img), c='red')
    # axs[1, 1].plot((potential[1:, y_cut])/4-0.5, c='orange')
    # axs[1, 1].set_title('y_cut on filtered')
    # axs[1, 1].set_xlim(x_lim)

    # FIG 5: FFT of raw img
    kaiser_window = np.outer(np.kaiser(img_verbose.shape[0], 8), np.kaiser(img_verbose.shape[1], 8))
    img_verbose_fft = fft.fftshift(fft.fft2(fft.ifftshift(img_verbose * kaiser_window)))
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    im = plt.imshow(np.flipud(np.abs(img_verbose_fft)), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), norm=mpl.colors.LogNorm(vmin=5), cmap='binary')
    ax.set_title('FFT of the raw img')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    fig.colorbar(im, ax=ax)

    # FIG 6: Filtered FFT of raw img
    img_verbose_fft = fft.fftshift(fft.fft2(fft.ifftshift(img_verbose)))
    rows, cols = img.shape
    crow, ccol = rows // 2, cols // 2
    y, x = np.ogrid[:rows, :cols]
    distance_sq = (x - ccol) ** 2 + (y - crow) ** 2
    cutoff_radius = 80
    mask = distance_sq <= (cutoff_radius ** 2)
    img_fft_filtered = img_verbose_fft * mask
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    im = plt.imshow(np.flipud(np.log1p(np.abs(img_fft_filtered*10))/np.log1p(10)), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), norm=mpl.colors.LogNorm(vmin=5), cmap='binary')
    ax.set_title('Filtered fft')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    fig.colorbar(im, ax=ax)

    # FIG 7: Plot of the cost function
    _, ax = plt.subplots(1, 1, figsize=(10, 10))
    img_verbose = img
    img_verbose[img_verbose <= 0] = 0
    potential[img_verbose <= 0] = 4
    im = plt.imshow(np.flipud(np.abs((img - (4 - potential)*np.max(img))**2)), extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap='Blues_r')
    ax.set_title('Difference between filtered img and potential on each pixels')
    ax.set_xlabel('x (pixels)')
    ax.set_ylabel('y (pixels)')
    _.colorbar(im, ax=ax)

    # Background fft plots
    # rec_windowed_img = np.real(fft.fftshift(fft.ifft2(fft.ifftshift(img_verbose_fft))))
    # _, ax = plt.subplots(1, 1, figsize=(10, 10))
    # im = plt.imshow(np.flipud(rec_windowed_img),  vmin=0, vmax=0.5, extent=(x_list.min(), x_list.max(), y_list.min(), y_list.max()), cmap=cmap)
    # ax.set_title('Img (red) and fitted potential (blue)')
    # ax.set_xlabel('x')
    # ax.set_ylabel('y')
    # _.colorbar(im, ax=ax)

    # _, ax = plt.subplots(1, 1, figsize=(10, 10))
    # im = plt.imshow(np.flipud(img_verbose[300:500,300:500]))
    # ax.set_title('Img (red) and fitted potential (blue)')
    # ax.set_xlabel('x')
    # ax.set_ylabel('y')
    # _.colorbar(im, ax=ax)

    # img_verbose_fft_background = fft.fftshift(fft.fft2(fft.ifftshift(img_verbose[300:500,300:500])))
    # _, ax = plt.subplots(1, 1, figsize=(10, 10))
    # im = plt.imshow(np.flipud(np.abs(img_verbose_fft_background)), norm=mpl.colors.LogNorm(vmin=5))
    # ax.set_title('Img (red) and fitted potential (blue)')
    # ax.set_xlabel('x')
    # ax.set_ylabel('y')
    # _.colorbar(im, ax=ax)
    plt.show()
    return