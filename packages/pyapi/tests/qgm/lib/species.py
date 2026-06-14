# -*- coding: utf-8 -*-
"""
Created on Mon Dec 05 10:20:49 2016

@author: Konrad

We derive all species classes from the base class Atom. For frames that don't
have atom character we use the species called 'n/a', for species that we don't
want to define (e.g. Cesium because we are not using it) we can assigna a
default species called X100. Species objects are necesary for analysis methods
that use mass, linewidth etc.

It is important to pupulate the dict

speciesdict = {}

Dictionary of species objects
HowTo:define Atom object for each species and populate the dict with a tag/name
e.g. 'rb' for Rb87 The label has to be the same as the one you give to the
image in the sequence.

--

Rb87:

We always assume D2 line properties unless otherwise specified.

Values taken from Naaman's thesis / D.A. Steck: Rubidium D-line data (2003)

K39:

We always assume D2 line properties unless otherwise specified.
If D1 is required, just define another 'species', such as K39-D1.

Values taken from Naaman's thesis / T. Tiecke: Properties of potassium (2010).

"""

#from ufloat.funits import kg, m, s, nm, us, ns, MHz
from scipy import constants
import numpy as np
from numpy import pi
import logging as log

kg = 1.
m = 1.
s = 1.
nm = 1.e-9
us = 1.e-6
ns = 1.e-9
MHz = 1.e-6


h = constants.h*kg*m**2/s
c = constants.c*m/s
u = constants.u*kg

speciesdict = {}

#==============================================================================
# Base class
#==============================================================================

class Atom(object):
    '''Base class that provides some framework for atom species'''
    def __init__(self):
        self.name = None
        self.wavelength = None
        self.lifetime = None
        self.linewidth = None # eg. 6MHz x 2pi
        self.mass = None
        self.trec = None
        self.tdoppler = None 

    @property
    def vrec(self):
        '''Recoil velocity in m/s'''
        return h/(self.wavelength*self.mass)

    @property
    def erec(self):
        '''Recoil energy in kHz'''
        return h/(2.*self.mass*self.wavelength**2)

    @property
    def i_sat(self):
        if self.wavelength is None:
            raise NotImplementedError
        else:
            return np.pi*h*c/\
            (3.*(self.wavelength)**3*self.lifetime)

    def opt_abs_x_section(self, intensity = None, detuning = 0*MHz):
        if self.wavelength is None:
            raise NotImplementedError
        else:
            if intensity is not None:
                return 3.*self.wavelength**2/(2.*np.pi)*1./\
                (1. + intensity/self.i_sat + (2*detuning/self.linewidth)**2)
            else:
                log.warning('No intensity value given. Assuming 0*i_sat.')
                return 3.*self.wavelength**2/(2.*np.pi)*1./\
                (1. + 0. + (2*detuning/self.linewidth)**2)

#==============================================================================
# Children classes
#==============================================================================

class X100(Atom):
    '''Default species if unkown species is passed'''
    def __init__(self):
        super(X100, self).__init__()
        self.wavelength = 780.241209686*nm
        self.lifetime = 26.24*ns
        self.linewidth = 6.065*MHz*2.*pi
        self.mass = 86.909180520*u
        self.name = 'default'
    def __getattribute__(self, attr):
        '''adding a warning to every call of X100 params'''
        my_attr = object.__getattribute__(self, attr)
        if not my_attr:
            raise Exception("Method {0} not implemented".format(my_attr))
        log.warning('No matching species found (see config/species.py)')
        return my_attr

speciesdict['k40'] = X100()
speciesdict['k40_1'] = X100()
#speciesdict[None] = X100()

class NA(Atom):
    '''
    Default species if tag 'None' is passed.
    n/a species (e.g. for dark frames)
    (this is necessary if no species was given)
    '''
    def __init__(self):
        super(NA, self).__init__()
#        self.wavelength = 780.241209686*nm
#        self.lifetime = 26.24*ns
#        self.linewidth = 6.065*MHz*2.*pi
#        self.mass = 86.909180520*u
        self.name = 'n/a'

speciesdict[None] = NA()

class K39(Atom):
    '''Derives common functions from parent class Atom'''
    def __init__(self):
        super(K39, self).__init__()
        self.wavelength = 766.700921822*nm #vacuum
        self.lifetime = 26.37*ns
        self.linewidth = 6.035*MHz*2.*pi
        self.mass = 38.96370668*u
        self.name = 'k39' #use extra name since python objects don't have
        # a __name__ attribute

speciesdict['k39'] = K39()

class Rb87(Atom):
    '''Derives common functions from parent class Atom'''
    def __init__(self):
        super(Rb87, self).__init__()
        self.wavelength = 780.241209686*nm
        self.lifetime = 26.24*ns
        self.linewidth = 6.065*MHz*2.*pi
        self.mass = 86.909180520*u
        self.name = 'rb'

speciesdict['rb'] = Rb87()


if __name__ == '__main__':

    try:
        a = Atom()
        print(a.i_sat())
    except NotImplementedError:
        print('No atom selected')
        pass
    
    default = X100()    
    
    print(default.linewidth, default.wavelength)
    
    print(default.i_sat)
