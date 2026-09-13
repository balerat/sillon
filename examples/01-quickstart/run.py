"""The smallest useful sillon script.

    python run.py
    sillon context          # see the run you just logged
    sillon show my_fit      # see its parameters and results
"""

import numpy as np

import sillonpy as sp

# Opens a run and seals it on the way out, even if the block raises.
with sp.track_run(run_name="my_fit", project_name="quickstart", author="you"):
    x = np.linspace(0, 10, 100)
    y = 1.3 * x + 5 + np.random.default_rng(0).normal(0, 0.4, x.size)

    # Inputs: what you chose.
    sp.log_param("degree", 1)
    sp.log_param("n_points", x.size)

    coef = np.polyfit(x, y, 1)

    # Outputs: what came out. Arrays are offloaded to HDF5 automatically.
    sp.log_result("coef", coef)
    sp.log_result("residual", float(np.std(y - np.polyval(coef, x))))

    sp.add_tag("baseline")
    sp.add_note("First attempt, noise sigma 0.4")

print("Logged. Now try:  sillon context")
