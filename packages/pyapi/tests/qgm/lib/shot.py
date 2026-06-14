# -*- coding: utf-8 -*-
"""
Created on Wed Jun 07 15:13:38 2017

@author: Konrad

Defines Shot object corresponding to one experimental run (one hdf5 file).

Given directory and hdffile, opens the hdf file. Userdata and Frame objects
can be accessed using self.userdata and self.get_frame.

If get_frame is called with framtype = 'OD' it searches for a pre-calculated
OD frame, if this is not found it calculates the OD frame using self.odframe
and self.calc_abs_frame_list.

Conventions:
a) all images have to have an attribute 'datatype' = "images"
b) the names of the images on hdf should contain frametype
    possibleframenames = ['abs', 'ref', 'dark', 'fluor', 'MOT', 'OD']
    (see config/camera.py)
    and species names according to speciesdict in config/species.py

The species and frametype attributes are stored with each Frame object.

The imagearrays are passed by reference and locating all frames of a typical
hdf file should not take longer than 4ms.
"""

from .frame import Frame
from .camera import *
from .species import *
import logging as log

from .qh5py import File
from .qh5py import Dataset
import os.path
from datetime import datetime
import time
import numpy as np
np.seterr(divide = 'ignore', invalid = 'ignore') #ignore divide by 0 for OD

class Scopedata(object):
    def __init__(self, xdata, ydata, names):
        self.xdata = xdata
        self.ydata = ydata
        self.names = names

class Shot():
    '''
    Main loading class corresponding to one experiment run ( = 'shot').
    '''
    def __init__(self, directory, hdffile):
        self._directory = directory
        self._filename = hdffile  
        self._path = os.path.join(self._directory, self._filename)
        
        self.hdffile = None
        
        self._framelist = [] #this is the main list of frame objects!
        # use property function frame_list to access the list
        self._scopedata = None

        self._userdata = {} # this is the main userdata dict!

        self.description = None # description of experimental run
        
        self._cameradict = cameradict
        self._speciesdict = speciesdict
        self._possibleframenames = possibleframenames
        
        self.__templist = [] # used internally and overridden for each camera
        #open the file
        self._open_file()    

    def __del__(self):
        try:
            if self.hdffile is not None:
                self.hdffile.close()
        except:
            pass #file already closed
    
    @property
    def userdata(self):
        if len(self._userdata) == 0:
            self._store_userdata()
        return self._userdata
    
    @property
    def timestamp(self):
        '''returns sequence start time as datetime.datetime object.'''
        try:
            my_str = self.hdffile['main/CompileTime'][()].decode()
            return datetime.strptime(my_str, '%a %b %d %H:%M:%S %Y')
        except Exception as e:
            log.exception(e)

    @property
    def frame_list(self):
        if len(self._framelist) == 0:
            self._store_frames()
            if len(self._framelist) == 0:
                raise ValueError('Shot does not contain any frames')
        return self._framelist

    @property
    def scope_data(self):
        if self._scopedata == None:
            self._store_scope()
            if self._scopedata == None:
                return
        return self._scopedata

    def get_frame(self, frametype = None, do_dark_subtract = 1):
        '''Returns the first frame of given type in the list
        of frames if it exists. Returns first frame in list otherwise.'''
        try:
            if frametype == 'OD':
                #calculate OD frame if not present
                try:
                    self.odframe()
                except ValueError as e:
                    log.error('Unable to calculate OD frame: {0}'.format(e))
            target = next((f for f in self.frame_list\
                        if f.frametype == frametype), self.frame_list[0])
            if (do_dark_subtract and target.frametype is 'MOT'):
                darkframe = next((f for f in self.frame_list\
                        if (f.frametype == 'dark' and f.camera == target.camera)), None)
                return subtract_dark(target, darkframe)
            else:
                return target
        except ValueError as e:
            log.error(e)

    def _open_file(self):
        '''Given the name and directory of hdf, open one hdf5 file
        store it as self.hdffile'''
        try:
            self.hdffile = File(self._path, 'r+')
        except IOError as e:
            log.warning(e)
            # Try read-only
            try:
                log.warning('Trying to open hdf read-only')
                self.hdffile = File(self._path, 'r')
            except Exception as e3:
                log.error('Unable to open {0}: {1}'.format(self._path, e3))
                self.hdffile = None
                raise
        except Exception as e2:
            log.error('Unable to open {0}: {1}'.format(self._path, e2))
            self.hdffile = None
            raise

    def _camera_name(self, camerastring):
        '''Reduces the hdf member string to just camera (last part of string)
        e.g. MotCam for system.soft.MotCam'''
        temp = str(camerastring).split('.')[-1]
        if temp in self._cameradict:
            return temp
        else:
            return None 

    def _species_name(self, framename):
        '''Finds any speciesname in framename'''
        temp = None
        for species in [x for x in self._speciesdict.keys() if x !=None]:
            if species in str(framename):
                temp = species
            else:
                pass
        return temp

    def _frame_type(self, framename):
        '''Finds any frame type in framename'''
        temp = None
        for frametype in self._possibleframenames:
            if frametype in str(framename):
                temp = frametype
            else:
                pass
        return temp

    def __store_temp(self, name, dataset):
        '''Populates a temporary list (new for each camera)
        according to the criteria/convention given in _possibleframenames.
        Not elegant, but it works. Do it this way since we cannot
        pass anything to the callable of visititems.'''
        if any(x in str(name) for x in self._possibleframenames):
            #print(name)
            self.__templist.append(name)

    def _store_frames(self):
        '''This is the main loop.
        First loop through all members ('groups') of one hdf file.
        Find the ones which are camera-type (ie. contain Cam or cam).
        Second loop through all datasets of one 'camera type' member.'''
        if self.hdffile is None:
            return
        i0 = 0 # check whether there are any camera types
        for member in self.hdffile:
 
            #check for image-type data in members of the hdf file
            if (self.hdffile[str(member)].attrs.get('datatype') == 'images'):
                #main recursive loop to populate __templist
                self.hdffile[str(member)].visititems(self.__store_temp)
                #loop through __templist
                for hdfdataset in self.__templist:
                    #print(member, hdfdataset)
                    # passing all information to one frame object
                    # array as hdf5 dataset
                    imagearray = self.hdffile[member + '/' + hdfdataset]
                    if not (type(imagearray) == Dataset):
                        log.error('Imagearray must be of type tools.qh5py.Dataset')
                        continue
                    # frame type as string
                    frametype = self._frame_type(hdfdataset)
                    # camera object stored in config.Camera
                    camera = self._cameradict[self._camera_name(member)]
                    # species object stored in config.Species
                    species = self._speciesdict[self._species_name(hdfdataset)]
                    im = Frame(imagearray, frametype, camera, species)
                    self._framelist.append(im)
                i0 += 1
                # empty the temporary list after each camera
                del self.__templist[:]
            else:
                pass
        if i0 == 0:
            log.warning('No camera-type dataset found in {0}.'.format(
            self._filename))

    def _store_scope(self):
        '''Checks whether the shot contains any scope traces. If it does,
        stores them in scope_list.'''
        if self.hdffile is None:
            return
        if 'system.soft.visa.scope' in self.hdffile:
            i0 = 0
            ydata = []
            names = []
            for trace in self.hdffile['system.soft.visa.scope']:
                if i0 == 0:
                    xdata = self.hdffile['system.soft.visa.scope/' + str(trace) + '/x']
                ydata.append(self.hdffile['system.soft.visa.scope/' + str(trace) + '/y'])
                names.append(str(trace))
                i0 += 1
            if i0 == 0:
                return
            self._scopedata = Scopedata(xdata, ydata, names)
        else:
            return

    def __store_param(self, name, dataset):
        '''
        when looping recursively, store all necessary parameters.
        '''
        if name == 'description':
            self.description = str(dataset.value)
        elif 'userdata/' in str(name):
            store_name = str(name.split('/')[-1])
            self._userdata[store_name] = dataset.value
        else:
            pass

    def _store_userdata(self):
        '''
        This is the second (recursive) loop for retreiving userdata.
        '''
        if self.hdffile is None:
            return
        if 'parameters' in self.hdffile:
            self.hdffile['parameters'].visititems(self.__store_param)
            if (self.description == None)|(self._userdata == {}):
                log.warning('No description or userdata found')
            else:
                pass
                #print('Successfully read description and userdata from {0}'\
                #.format(self._filename))
        else:
            log.warning('No parameters found in hdf5 file')

    def odframe(self, camera = None, species = None):
        '''Checks for existing OD frames in _framelist.
        Calculates the OD frame if it does not already exist.
        See docstring for calc_abs_frame_list for camera/species handling.'''
        if not 'OD' in [f.frametype for f in self.frame_list]:
            
            self.frame_list
            temp = self.calc_abs_frame_list(camera = camera, species = species)
            self._framelist.append(temp)
            mypath = '/' + temp.camera.hdfpath + temp.camera.name +'/'+ \
                    'OD_' + temp.species.name
            #print(mypath)
            # if od frame exists (shouldn't), remove it:
            if self.hdffile.__contains__(mypath):
                del self.hdffile[mypath]
            self.hdffile.create_dataset(mypath, data=temp.imagearray)
            #log.debug('Successfully saved OD frame')
        else:
            #log.debug('Found OD image in list of frames')
            temp = next((f for f in self._framelist if f.frametype == 'OD'), None)
        return temp

    def calc_abs_frame_list(self, camera = None, species = None):
        '''Calculate the OD image from a given list of frames
        (if they include at least one abs and one ref image) and
        returns a new frame object (type 'OD') with the same attributes as the abs
        frame (if no camera or species is specified).
        If this function is called with a given camera and species, only the
        specified OD image is calculated.
        
        We populate the dictionary framedict from self._framelist.
        for most practical purposes it will contain all elements of self._framelist.
        Only if there is an ambiguity (e.g. two images from different cameras of
        the same species or two images from one camera of different species.) we
        actually need the arguments camera and species.'''
        
        framedict = {}
    
        if (camera is None)|(species is None):
            if len(set([f.species.name for f in self._framelist \
            if not (f.species.name == 'n/a')])) > 1:
                msg = 'Framelist contains more than one species'
                log.warning(msg)
                raise Warning(msg)
            # if no camera and species given, just convert the whole framelist
            # into a dict
            for frame in self._framelist:
                framedict[frame.frametype] = frame
        else:
            print('Searching for frames matching attrs \'{0}\' and \'{1}\''.format(
            camera, species))
            for frame in self._framelist:
                if frame.camera.name == camera:
                    if frame.species.name == species:
                        framedict[frame.frametype] = frame
                    elif frame.species.name == 'default':
                        # this is necessary to carry dark frames
                        framedict[frame.frametype] = frame
                    else:
                        continue
                else:
                    continue
        
        def remove_inf(arr):
            '''remove any inf and large OD values and replace them by np.nan'''
            arr[np.abs(arr) == np.inf] = np.nan
            # arr[arr > MAX_OD] = np.nan
            return arr
        
        if not ('abs' and 'ref') in framedict:
            #log.info(framedict)
            msg1 = 'abs or ref frame not found'
            #this exception is caught up in get_frame
            raise ValueError(msg1)
        else:
            if 'dark' in framedict:
                # passing the arrays directly saves time (although it looks ugly)
                # since at this stage they will be still passed by reference from
                # the hdf file.
                if self.userdata['do_non_linear_od_formula'] == 0:
                    do_nonlinear_od_cal= 0
                else:
                    do_nonlinear_od_cal= 1
                
                if 'latt_Z_removal' in framedict:
                    odframe = Frame(
                                remove_inf(
                                    calc_abs_frame(
                                        framedict['abs'],
                                        framedict['ref'],
                                        self.userdata['imaging_exposure'],
                                        do_nonlinear_od_cal,
                                        framedict['dark'],
                                        framedict['latt_Z_removal'])),
                                        frametype = 'OD',
                                        camera = framedict['abs'].camera,
                                        species = framedict['abs'].species)
                else:
                    odframe = Frame(
                                remove_inf(
                                    calc_abs_frame(
                                        framedict['abs'],
                                        framedict['ref'],
                                        self.userdata['imaging_exposure'],
                                        do_nonlinear_od_cal,
                                        framedict['dark'])),
                                        frametype = 'OD',
                                        camera = framedict['abs'].camera,
                                        species = framedict['abs'].species)

            else:
                odframe = Frame(
                            remove_inf(
                                calc_abs_frame(
                                    framedict['abs'],
                                    framedict['ref'])),
                                    frametype = 'OD',
                                    camera = framedict['abs'].camera,
                                    species = framedict['abs'].species)
            return odframe

def subtract_dark(frame, darkframe, dtype = np.int16):
    if darkframe is None:
        return frame
    else:
        log.info('Subtracting dark image.')
        framearray = np.array(frame.imagearray, dtype = dtype)
        darkarray = np.array(darkframe.imagearray, dtype = dtype)
        subarray = framearray - darkarray
        subtracted = Frame(subarray, frame.frametype, frame.camera, frame.species)
        return subtracted

def calc_abs_frame(absframe, refframe,exposure,do_nonlinear_od_cal, darkframe = None, latt_Z_removal_frame=None):
    print('Calculating OD frame...')
    if darkframe is not None:
        if latt_Z_removal_frame is not None:
            return calc_abs(absframe.imagearray,
                            refframe.imagearray,
                            exposure,
                            do_nonlinear_od_cal,
                            darkframe.imagearray,
                            latt_Z_removal_frame.imagearray
                           )
        else:
            return calc_abs(absframe.imagearray,
                            refframe.imagearray,
                            exposure,
                            do_nonlinear_od_cal,
                            darkframe.imagearray
                           )
    else:
        return calc_abs(absframe.imagearray, refframe.imagearray)

def calc_abs(absarray, refarray, exposure,do_nonlinear_od_cal, darkarray = None, latt_Z_removal_frame = None, dtype = np.float32):
    '''Returns an array with optical density per pixel.
    This assumes that the images are already cleaned up, i.e.
    saturated areas removed. Arrays can include np.nan.
    
    tried a couple of float types but np.float32 seemed to be fastest for a
    typical absorption image'''
    if latt_Z_removal_frame is not None:
        dark_arr_ref = np.array(darkarray, dtype = dtype)
        dark_arr_abs = np.array(latt_Z_removal_frame, dtype = dtype)
        if do_nonlinear_od_cal == 1:
            print('use non-linear OD formula')
            return -1.375*np.log((np.array(absarray, dtype = dtype) - dark_arr_abs)/\
            (np.array(refarray, dtype = dtype) - dark_arr_ref)) + (np.array(refarray, dtype = dtype) - (np.array(absarray, dtype = dtype)-dark_arr_abs+dark_arr_ref))/(9880*(exposure/(70*us)))
        else:
            print('use old OD formula')
            return -np.log((np.array(absarray, dtype = dtype) - dark_arr_abs)/\
            (np.array(refarray, dtype = dtype) - dark_arr_ref))
    elif darkarray is not None:
        dark_arr = np.array(darkarray, dtype = dtype)
        if do_nonlinear_od_cal == 1:
            print('use non-linear OD formula')
            return -1.375*np.log((np.array(absarray, dtype = dtype) - dark_arr)/\
            (np.array(refarray, dtype = dtype) - dark_arr)) + (np.array(refarray, dtype = dtype) - np.array(absarray, dtype = dtype))/(9880*(exposure/(70*us)))
        else:
            print('use old OD formula')
            return -np.log((np.array(absarray, dtype = dtype) - dark_arr)/\
            (np.array(refarray, dtype = dtype) - dark_arr))
    else:
        return -np.log((np.array(absarray, dtype = dtype))/\
        (np.array(refarray, dtype = dtype)))

def print_frame_list(framelist):
    '''Helper function to quickly print the contents of a framelist.'''
    if len(framelist) == 0:
        raise Exception('Unable to find any images')
    else:
        print('Hdf file contains {0} frames'.format(len(framelist)))
        for frame in framelist:
            print('{0}: of species {1} taken on {2}'.format(
            frame.frametype, frame.species.name, frame.camera.name))