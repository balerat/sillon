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


def delete_run(run: Run) -> dict:
    """Permanently deletes a run (its stored data and database row).

    Convenience wrapper around `Run.delete()`.

    Args:
        run (Run): The run handle to delete.

    Returns:
        dict: `{"status": "success", "deleted": str, "freed_bytes": int}`,
            or an error status if the run no longer exists.
    """
    if not isinstance(run, Run):
        raise TypeError(
            "delete_run expects a Run object; to delete by name use "
            "project.delete_run(name)."
        )
    return run.delete()


__all__ = ["Project", "load_project", "Run", "RunCollection", "delete_run"]
