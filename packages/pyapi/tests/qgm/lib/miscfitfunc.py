# -*- coding: utf-8 -*-
"""
Created on Tue Jan 10 14:56:15 2017

@author: Konrad
"""

import numpy as np
from scipy import constants
from .unitsReplacement import m, s, kg, K
from scipy.special import wofz

g = constants.g
kB = constants.k*kg*m**2/(s**2 * K)

def hyperbola(t, *p):
    sig0,v = p
    return np.sqrt(sig0**2+(v**2)*(t**2))

def linear(t, off, v):

    return v*t+off

def lorentzian(w, *p):
    Gamma, w0, off, A = p
    return off + A/((w-w0)**2+(0.5*Gamma)**2)

def double_lorentz(x, *p):
    gamma1, w1, A1, gamma2, w2, A2, off= p
    return off + A1/((x-w1)**2+(0.5*gamma1)**2) + A2/((x-w2)**2+(0.5*gamma2)**2)

def parabola(t, *p):
    a, v, c = p
    return 0.5*a*t**2 + v*t + c

def parabola_alt(t, *p):
    a, t0, c = p
    return a*(t - t0)**2 + c

def gravity_acc(t, *p):
    m, c = p
    return (-0.5*g*t**2 + c)/m

def gravity_acc_lin(t, *p):
    m, v0, c = p
    return m*(-0.5*g*t**2 + v0*t + c)

def gauss(x, *p):
    sigma, x0, A, c = p
    return A*np.exp(-(x-x0)**2/(2 * sigma**2)) + c

def double_gauss(x, *p):
    sigma1, sigma2, x1, x2, A1, A2, c= p
    return A1*np.exp(-(x-x1)**2/(2 * sigma1**2)) + A2*np.exp(-(x-x2)**2/(2 * sigma2**2)) + c

def double_voigt(x, *p):
    sigma1, x1, sigma2, x2, A2, off = p
    gamma1 = sigma1
    gamma2 = sigma2

    voigt1 = 11.8*np.real(wofz((x - x1 + 1j*gamma1)/(np.sqrt(2)* sigma1)))/(np.sqrt(2*np.pi)*sigma1)
    voigt2 = A2*np.real(wofz((x - x2 + 1j*gamma2)/(np.sqrt(2) * sigma2)))/(np.sqrt(2*np.pi)*sigma2)

    return voigt1 + voigt2 + off

def parabola(x, *p):
    a, x0, b = p
    return -a*(x-x0)**2 + b

def exponentialnooffset(t, *p):
	a, tau = p
	return a*np.exp(-t/tau)

def exponentialoffset(t, *p):
	a, b, tau = p
	return a*np.exp(-t/tau) + b

def tof_temperature(sigma, mass, tof):
    '''Calculate temperature after ToF,
    neglecting finite size of initial cloud.
    Accepts sigma in meters, mass in kg and tof in s'''
    return mass*sigma**2/(3.*kB*tof**2)
    
def cosine(t, *p):
#    f, amp, offset, t0 = p
    f, amp, offset, t0, phase = p
    return amp*np.cos(2*np.pi*f*(t-t0)+phase) + offset

def rotatedcos(t, *p):
    theta, amp, f, t0 = p
    return np.sin(theta)*amp*np.cos(2.*np.pi*f*(t-t0)), np.cos(theta)*amp*np.cos(2.*np.pi*f*(t-t0))

def exp_rise(t, *p):
    amp, tau, off = p
    return amp*(1-np.exp(-t/tau)) + off

def tanh(t, *p):
    amp, width, t0, c = p
    return amp*np.tanh((t-t0)/width) + c