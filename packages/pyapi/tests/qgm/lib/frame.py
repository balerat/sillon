# -*- coding: utf-8 -*-
"""
Created on Tue Nov 29 16:46:04 2016

@author: Konrad

This module defines the Frame class.

"""

import numpy as np
import logging as log

class Frame():
    def __init__(self, imagearray,
                 frametype = None, camera = None, species = None):
        self._imagearray = imagearray
        self.frametype = frametype
        self.camera = camera
        self.species = species

        # Convert NaNs to zero if True
        self._nan_to_num = False
        
        # gather some basic information about imagearray
        self.shape = self.imagearray.shape
        if len(self.shape) != 2:
            raise ValueError('Frame object requires a 2d array')
        
        self.dtype = self.imagearray.dtype
        if self.dtype in [np.uint16, np.uint8, int]:
            # check for saturation only if int type
            self.satval = np.iinfo(self.dtype).max
        
        # initialise roi full-size
        self._roi = (0, self.shape[0], 0, self.shape[1])
        
        # initialise ref as None
        self._refroi = None

    def roichecker(self, roi):
        '''Returns roi if it is in correct format (see frame.roi for info),
        raises error otherwise.'''
        if (type(roi) is tuple) and (len(roi) is 4):
            if (roi[1] > roi[0]) and (roi[3] > roi[2]) and \
                    (roi[1] <= self.shape[0]) and (roi[3] <= self.shape[1]):
                return roi
            else:
                print(self.shape)
                raise ValueError(
                'ROI has to be (ymin, ymax, xmin, xmax). Got {0} instead.'.\
                format(roi))
        else:
            raise ValueError(
            'ROI has to be 4-tuple (ymin,ymax, xmin,xmax). Got {0} instead.'.\
            format(roi))

    def typechecker(self, frametype):
        '''Generic check function to be used for analysis.'''
        if self.frametype == frametype:
            return 0
        else:
            msg = 'Expected frame type {0} but got {1} instead'.format(
                frametype, self.frametype)
            log.error(msg)
            raise ValueError(msg)

    @property
    def roi(self):
        return self._roi
    
    @roi.setter
    def roi(self, new_roi):
        '''Region of interest hast to be 4-tuple in the format
        (ymin, ymax, xmin, xmax).
        We are using the numpy convention: row-major order.
        Here x value = one column = second index in a 2d numpy array.'''
        self._roi = self.roichecker(new_roi)
    
    @property
    def image_cropped(self):
        '''Returns the image within the ROI, which is
        defined as (ymin, ymax, xmin, xmax).
        
        For any array we always assume the first index to be the y-axis,
        and the second index to be the x-axis (numpy, row-major order).
        Eg. an image of shape (2560, 2160) would have
        2560 rows (so first index: y-axis)
        and 2160 columns (second index: x-axis).
        So calling array[123,:] gives a slice along x at y = 123.'''
        return self.imagearray[self.roi[0]:self.roi[1],
                               self.roi[2]:self.roi[3]]

    @property
    def nan_to_num(self):
        '''Switch for NaN handling. If True, all NaNs will be converted to
        zeros, if False everything is kept as is.'''
        return self._nan_to_num

    @nan_to_num.setter
    def nan_to_num(self, value):
        self._nan_to_num = value

    @property
    def imagearray(self):
        '''Convert NaNs to zero if necessary.'''
        if self.nan_to_num:
            return np.nan_to_num(self._imagearray)
        else:
            return self._imagearray

    @property
    def x_coord_crop(self):
        '''Returns a 1d array (in the roi) of coordinates along x
        see image_cropped for definition of what 'x' means'''
        return np.arange(self.roi[2], self.roi[3])
    
    @property
    def y_coord_crop(self):
        '''Returns a 1d array (in the roi) of coordinates along y
        see image_cropped for definition of what 'y' means'''
        return np.arange(self.roi[0],self.roi[1])

    @property
    def x_coord(self):
        '''Returns a 1d array (of the whole image) of coordinates along x'''
        return np.arange(0, self.shape[1])
    
    @property
    def y_coord(self):
        '''Returns a 1d array (of the whole image) of coordinates along x'''
        return np.arange(0, self.shape[0])
    
    @property
    def mesh_grid(self):
        '''Returns a np.meshgrid (i.e. a list of two 2d arrays which can be
        used to evaluate f(x,y) functions on the x,y grid).
        Here x comes first!'''
        return np.meshgrid(self.x_coord, self.y_coord)
        
    @property
    def mesh_grid_crop(self):
        '''Returns a np.meshgrid (i.e. a list of two 2d arrays which can be
        used to evaluate f(x,y) functions on the x,y grid).
        Here x comes first!'''
        return np.meshgrid(self.x_coord_crop, self.y_coord_crop)

    @property
    def x_px_sum(self):
        '''Returns a 1d array: px sum (whole image) along y for each x-value'''
        return np.nansum(self.imagearray, axis = 0) # sum along y
    
    @property
    def y_px_sum(self):
        '''Returns a 1d array: px sum (whole image) along x for each y-value'''
        return np.nansum(self.imagearray, axis = 1) # sum along x

    @property
    def x_px_sum_crop(self):
        '''Returns a 1d array: px sum (crop image) along y for each x-value'''
        return np.nansum(self.image_cropped, axis = 0) # sum along y
    
    @property
    def y_px_sum_crop(self):
        '''Returns a 1d array: px sum (crop image) along x for each y-value'''
        return np.nansum(self.image_cropped, axis = 1) # sum along x
    
    def x_cut(self, y):
        '''returns cut along x-axis (whole image) for given y coordinate'''
        return self.imagearray[y,:]
    
    def y_cut(self, x):
        '''returns cut along y-axis (whole image) for given x coordinate'''
        return self.imagearray[:,x]

    def x_cut_crop(self, y):
        '''returns cut along x-axis (cropped image) for given y coordinate.
        which is referenced to the original (uncropped) imagearray.
        (Otherwise we'd have to deal with relative coordinates.)'''
        y_ref_to_roi = y - self.roi[0]
        if y_ref_to_roi < 0:
            raise ValueError('y coordinate is outside ROI. Use x_cut instead.')
        else:
            return self.image_cropped[y_ref_to_roi,:]

    def y_cut_crop(self, x):
        '''returns cut along y-axis (cropped image) for given x coordinate
        which is referenced to the original (uncropped) imagearray.
        (Otherwise we'd have to deal with relative coordinates.)'''
        x_ref_to_roi = x - self.roi[2]
        if x_ref_to_roi < 0:
            raise ValueError('x coordinate is outside ROI. Use y_cut instead.')
        else:
            return self.image_cropped[:, x_ref_to_roi]

    @property
    def min_value(self):
        '''Returns minimum value of the whole imagearray'''
        return np.nanmin(self.imagearray)

    @property
    def max_value(self):
        '''Returns maximum value of the whole imagearray'''
        return np.nanmax(self.imagearray)

    @property
    def min_value_crop(self):
        '''Returns minimum value of the cropped imagearray'''
        return np.nanmin(self.image_cropped)

    @property
    def max_value_crop(self):
        '''Returns maximum value of the cropped imagearray'''
        return np.nanmax(self.image_cropped)

    @property
    def refroi(self):
        return self._refroi
    
    @refroi.setter
    def refroi(self, new_roi):
        '''Region of interest hast to be 4-tuple in the format
        (ymin, ymax, xmin, xmax).
        We are using the numpy convention: row-major order.
        Here x value = one column = second index in a 2d numpy array.'''
        self._refroi = self.roichecker(new_roi)
    
    @property
    def roisize(self):
        return self.image_cropped.size
    
    @property
    def refarray(self):
        '''Returns the array within the refroi'''
        if self._refroi is None:
            raise TypeError('refarray requires refroi to be not None')
        else:
            return self.imagearray[self.refroi[0]:self.refroi[1],
                               self.refroi[2]:self.refroi[3]]
        