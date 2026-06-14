import sillonpy as sl
import numpy as np

super_param = np.linspace(1,10,100)

def poly_trome(x):
    return 1.323 * x + 323

sl.init("basic01")

sl.log_param("super_param", super_param)

coef = np.polyfit(super_param, poly_trome(super_param), 1)

sl.log_result("coef", coef)

sl.add_note("Mhmm let's see if it worked")

