"""Figures that remember which data drew them, and runs that remember their parent.

    python run.py
    sillon show baseline -f       # the figure, and what it was built from
    sillon lineage refined        # what this run derives from
"""

import numpy as np

import sillonpy as sp

try:
    import matplotlib
    matplotlib.use("Agg")          # no display needed
    import matplotlib.pyplot as plt
except ImportError:  # pragma: no cover
    raise SystemExit("This example needs matplotlib: pip install matplotlib")

rng = np.random.default_rng(0)
x = np.linspace(0, 10, 200)
y = 1.3 * x + 5 + rng.normal(0, 0.6, x.size)

# --- a baseline run -------------------------------------------------------
with sp.track_run(run_name="baseline", project_name="provenance", author="you"):
    sp.log_param("degree", 1)
    coef = np.polyfit(x, y, 1)
    sp.log_result("coef", coef)

    fig, ax = plt.subplots()
    ax.plot(x, y, ".", label="data")
    ax.plot(x, np.polyval(coef, x), label="fit")
    ax.legend()

    # `used=` is the point: six months from now this figure can still tell you
    # which logged values produced it.
    sp.log_figure(fig, name="fit", used=["coef", "degree"],
                  caption="Linear fit over the noisy sample")
    plt.close(fig)

# --- a run that derives from it -------------------------------------------
# `inherit` records a lineage edge only; nothing is copied. The child logs its
# own parameters, and you can walk back to the parent later.
with sp.track_run(run_name="refined", project_name="provenance",
                  author="you", inherit="baseline"):
    sp.log_param("degree", 3)
    coef3 = np.polyfit(x, y, 3)
    sp.log_result("coef", coef3)
    sp.add_note("Higher degree, same data as baseline")

print("Logged. Now try:  sillon show baseline -f   and   sillon lineage refined")
