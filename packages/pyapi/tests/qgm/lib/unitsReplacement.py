#A simple replacement for ufloat for versions of python where it becomes difficult to install and have working
#Note that this doesn't work nicely for dBm so be careful with that

#TEMPERATURE
K = 1.0
mK = 1.0e-3
uK = 1.0e-6
nK = 1.0e-9

#MASS
kg = 1.0
gram = 1.0e-3

#POWER
kW = 1.0e3
W = 1.0
mW = 1.0e-3
uW = 1.0e-6
nW = 1.0e-9

#VOLTAGE
kV = 1.0e3
V = 1.0
mV = 1.0e-3
uV = 1.0e-6
nV = 1.0e-9

#CURRENT
kA = 1.0e3
A = 1.0
mA = 1.0e-3
uA = 1.0e-6
nA = 1.0e-9

#TIME
hour = 3600.0
minute = 60.0
s = 1.0
ms = 1.0e-3
us = 1.0e-6
ns = 1.0e-9

#DISTANCE
km = 1.0e3
m = 1.0
dm = 1.0e-1
cm = 1.0e-6
mm = 1.0e-3
um = 1.0e-6
nm = 1.0e-9
Angstrom = 1.0e-10

#FREQUENCY
THz = 1.0e12
GHz = 1.0e9
MHz = 1.0e6
kHz = 1.0e3
Hz = 1.0
mHz = 1.0e-3
uHz = 1.0e-6
nHz = 1.0e-9

#ENERGY
kJ = 1.0e3
J = 1.0
mJ = 1.0e-3
uJ = 1.0e-6
nJ = 1.0e-9
eV = 1.602177e-19 #https://physics.nist.gov/cgi-bin/cuu/Value?evj

def rescale(value, oldUnit=1.0, newUnit=1.0):
    return value*oldUnit/newUnit
