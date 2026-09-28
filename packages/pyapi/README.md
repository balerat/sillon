# sillonpy

The logging client, imported inside a simulation script.

```python
import sillonpy as sp

with sp.track_run(run_name="my_fit", project_name="demo"):
    sp.log_param("degree", 1)
    sp.log_result("coef", coef)
```

| Module | Role |
|---|---|
| `api.py` | the functions users call |
| `tracker.py` | the run's client-side state; wraps each API call as a command |
| `serverCom.py` | the connection to the project daemon |
| `daemon.py` | spawning the daemon and checking it is alive |
| `metadata.py` | python-specific metadata, and the sources behind a code version |

Full documentation: [Logging runs](../../docs/guide/logging.md) ·
[API reference](../../docs/reference/sillonpy.md)
