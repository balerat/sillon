# `sillonpy` — logging API

The client you import inside a simulation script. See
[Logging runs](../guide/logging.md) for worked examples.

```python
import sillonpy as sp
```

## Opening a run

::: sillonpy.api
    options:
      members:
        - track_run
        - init
        - force_dump
        - track

## Logging values

::: sillonpy.api
    options:
      members:
        - log_param
        - log_result
        - log_figure
        - add_metadata
        - log_metadata
        - add_note
        - add_tag
