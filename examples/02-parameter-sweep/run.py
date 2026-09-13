"""A parameter sweep: many runs from one script, then rank them.

    python run.py
    sillon context
    sillon search -p degree=3
"""

import numpy as np

import sillonpy as sp

rng = np.random.default_rng(0)
x = np.linspace(0, 10, 200)
y = 0.5 * x**3 - 2 * x**2 + 3 * x + rng.normal(0, 5, x.size)

for degree in (1, 2, 3, 4, 5):
    for ridge in (0.0, 0.1):
        # One run per combination. track_run opens and seals each one, so a
        # failure in the middle of the sweep costs you that run, not all of them.
        with sp.track_run(project_name="sweep", author="you"):
            sp.log_param({"degree": degree, "ridge": ridge})

            coef = np.polyfit(x, y, degree)
            rmse = float(np.sqrt(np.mean((y - np.polyval(coef, x)) ** 2)))

            sp.log_result("coef", coef)
            sp.log_result("rmse", rmse)
            sp.add_tag("sweep")

print("Logged 10 runs. Now try:  python analyse.py")
