# -*- coding: utf-8 -*-
"""
Created on Mon Dec 05 15:05:26 2016

@author: Konrad

Do camera configuration here. Define new class (at the bottom) for each camera,
deriving from base class Camera. It is important to give it the attribute
'name' with the same name as the InputModule on qcontrol, and the populate the
cameradict afterwards. core/shot.Shot will try to assign camera objects to each
frame according to this dict of name assignments.

possibleframenames will be used by core/shot.Shot to define the frametype of
each frame found in a hdf.

Important variables: cameradict, possibleframenames.

If cameradict and possibleframenames are not populated properly this leads to
annoying errors: the OD frame will be calculated with the DummyCam attribute
meaning that no pixel sixe and magn. values will be found for analysis. If this
happens, re-calculate the OD image using Shot.odframe with a given camera and
species as argument.
"""

#from ufloat.funits import um

um = 1.0e-6

#==============================================================================
# config
#==============================================================================

cameradict = {} #populate this dict after defining each camera class
# ugly but it works: we need to have a look-up table for each camera

# names of frame type to search for in loop
possibleframenames = ['abs', 'ref', 'dark', 'fluor', 'MOT', 'OD','latt_Z_removal']

#==============================================================================
# parent class
#==============================================================================

class Camera():
    '''
    parameters:
    _pixelpitch is width (or height, should be square) of one pixel
    _magnification is self-explanatory
    '''
    def __init__(self):
        self._pixelpitch = None
        self._magnification = None
        self.name = None
        self.hdfpath = 'system.soft.' # member name of camera in hdf file
        # (this is used to store the od frame to the right location)
        self.sensitivity = None #electrons per A/D count
        # sensitivity might depend of shutter/readout settings!
    
    @property
    def pixel_area(self):
        if self._pixelpitch is None:
            raise NotImplementedError
        else:
            return self._pixelpitch**2

    @property
    def pixelpitch(self):
        if self._pixelpitch is None:
            raise NotImplementedError
        else:
            return self._pixelpitch    
    
    @property
    def magnification(self):
        if self._magnification is None:
            raise NotImplementedError
        else:
            if self._magnification <= 0.:
                raise Exception('Negative magnification')
            else:
                return self._magnification
    
    @property
    def pixel_area_eff(self):
        if self._pixelpitch is None or self._magnification is None:
            raise NotImplementedError
        else:
            return (self._pixelpitch*self._magnification)**2

    @property
    def px(self):
        return self.pixelpitch*self.magnification

    def qe(self, wavelength):
        '''Quantum efficiency as a function of wavelength (in nm)'''
        raise NotImplementedError

#==============================================================================
# Default camera (dummy)
#==============================================================================

class DummyCam(Camera):
    def __init__(self):
        super(DummyCam, self).__init__()
        self._pixelpitch = 10.*um
        self._magnification = 1.
        self.name = 'DefaultCam'
    def __getattribute__(self, attr):
        '''adding a warning to every call of DummyCam params'''
        my_attr = object.__getattribute__(self, attr)
        if not my_attr:
            raise Exception("Method {0}} not implemented".format(my_attr))
        return my_attr

cameradict[None] = DummyCam() #assign dummy camera if camera name
    #does not match any of the above

#==============================================================================
# YAxisCam (Andor Zyla)
#==============================================================================
    
class YAxisCam(Camera):
    def __init__(self):
        super(YAxisCam, self).__init__()
        self._pixelpitch = 6.5*um
        self._magnification = 1/12.#1/3.4#1.264#2018/08/19 (was 1.004 before)
        self.name = 'YAxisCam'
        self.sensitivity = 0.49 #global shutter, 560MHz readout, low noise&
        #high well capacity setting

    def qe(self, wavelength):
        '''Quantum efficiency (eg. 0.37) as a function of wavelength (in nm).
        This is a rough estimate from the Andor website.'''
        return -0.00201*(wavelength - 965.)

cameradict['YAxisCam'] = YAxisCam()

#==============================================================================
# Mot camera (IDS uEye UI-1252LE-M)
#==============================================================================

class MotCam(Camera):
    def __init__(self):
        super(MotCam, self).__init__()
        self._pixelpitch = 4.5*um
        self._magnification = 5./1.
        self.name = 'MotCam'

cameradict['MotCam'] = MotCam()


#==============================================================================
# Dipole X camera (IDS uEye UI-1252LE-M)
#==============================================================================

class DipoleXCam(Camera):
    def __init__(self):
        super(DipoleXCam, self).__init__()
        self._pixelpitch = 4.5*um
        self._magnification = 1.23592#1/0.802
        self.name = 'DipoleXCam'

cameradict['DipoleXCam'] = DipoleXCam()

class DipoleXCam_new(Camera):
    def __init__(self):
        super(DipoleXCam_new, self).__init__()
        self._pixelpitch = 4.5*um
        self._magnification = 1.23592#1/0.802
        self.name = 'DIPOLE_X_CAM'
        self.hdfpath = ''
cameradict['DIPOLE_X_CAM'] = DipoleXCam_new()

#==============================================================================
# Dipole Y camera (IDS uEye UI-1252LE-M)
#==============================================================================

class DipoleYCam(Camera):
    def __init__(self):
        super(DipoleYCam, self).__init__()
        self._pixelpitch = 4.5*um
        self._magnification = 1.226
        self.name = 'DipoleYCam'

cameradict['DipoleYCam'] = DipoleYCam()

#==============================================================================
# Dipole Y camera (IDS uEye UI-1252LE-M)
#==============================================================================

class DiagonalCam(Camera):
    def __init__(self):
        super(DiagonalCam, self).__init__()
        self._pixelpitch = 4.5*um
        self._magnification = 0.19459
        self.name = 'DiagonalCam'

cameradict['DiagonalCam'] = DiagonalCam()

#==============================================================================
# Transport camera (IDS uEye UI-1252LE-M)
#==============================================================================

class TransportCam(Camera):
    def __init__(self):
        super(TransportCam, self).__init__()
        self._pixelpitch = 4.5*um
        self._magnification = 0.4096
        self.name = 'TransportCam'

cameradict['TransportCam'] = TransportCam()


#==============================================================================
# Dipole Y camera (IDS uEye UI-1252LE-M)
#==============================================================================

class DMantaCam(Camera):
    def __init__(self):
        super(DMantaCam, self).__init__()
        self._pixelpitch = 5.86*um
        self._magnification = 0.32608
        self.name = 'DMantaCam'
        # necessary since it is different from all others:
        self.hdfpath = 'system.soft.avtcams.'

cameradict['DMantaCam'] = DMantaCam()

#==============================================================================
# Polar molecules @MPQ
#==============================================================================

class GlassCellHor(Camera):
    def __init__(self):
        super(GlassCellHor, self).__init__()
        self._pixelpitch = 10*um
        self._magnification = 1.
        self.name = 'glasscellhor'

cameradict['glasscellhor'] = GlassCellHor()

if __name__ == '__main__':
    cam = MotCam()
    print('Camera {0} has pixelpitch {1}\n\
    and a resulting effective pixel area of\n {2}'.format(
                                    cam.name,
                                    cam._pixelpitch,
                                    cam.pixel_area_eff))
