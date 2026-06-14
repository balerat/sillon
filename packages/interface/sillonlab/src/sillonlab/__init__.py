"""sillonlab: the analysis library of the sillon toolchain.

Load a sillon project from a python script or a jupyter notebook and explore
its logged runs, the same way silloncli does from the shell.

Example:
    ```python
    import sillonlab as sl

    project = sl.load_project("path/to/project")
    print(project.runs().list())

    run = project.get("my_run")
    print(run.parameters)
    data = run.load_result("coef")
    ```
"""

from sillonlab.project import Project, load_project
from sillonlab.run import Run, RunCollection

__all__ = ["Project", "load_project", "Run", "RunCollection"]
