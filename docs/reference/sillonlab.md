# `sillonlab` — analysis API

Load projects and explore their runs from a script or a notebook. See
[Querying and analysis](../guide/analysis.md) for worked examples.

```python
import sillonlab as sl
```

## Finding and loading projects

::: sillonlab.projects
    options:
      members:
        - list_projects
        - open_project

::: sillonlab
    options:
      members:
        - load_project
      show_submodules: false

## Project

::: sillonlab
    options:
      members:
        - Project
      show_submodules: false

## Run and RunCollection

::: sillonlab
    options:
      members:
        - Run
        - RunCollection
        - delete_run
      show_submodules: false
