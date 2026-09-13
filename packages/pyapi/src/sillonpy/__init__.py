"""sillonpy — the logging client you import inside a simulation script.

    import sillonpy as sp

    with sp.track_run(run_name="my_fit", project_name="demo"):
        sp.log_param("degree", 1)
        sp.log_result("coef", coef)

Everything you log is sent to a per-project background daemon, which writes it
to `.sillon/` (SQLite for the light values, HDF5 for the heavy arrays). You
never start that daemon yourself.
"""

from .api import (
    init,
    track,
    track_run,
    force_dump,
    log_param,
    log_result,
    log_figure,
    add_metadata,
    log_metadata,
    add_note,
    add_tag,
)

__all__ = [
    "init",
    "track",
    "track_run",
    "force_dump",
    "log_param",
    "log_result",
    "log_figure",
    "add_metadata",
    "log_metadata",
    "add_note",
    "add_tag",
]
