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
from sillonlab.projects import list_projects, open_project
from silloncommon.access_log import clear as _clear_reads, reads as _reads
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


def forget_reads() -> None:
    """Forget which runs' data this session has read.

    A run logged in this process records a parent edge for every run whose data
    it loaded, so you never have to write `inherit=`. In a long exploratory
    session that can attach browsing you did an hour ago to the run you log
    now — call this to start the provenance clean.

    Example:
        ```python
        for run in project.runs():
            inspect(run.load_result("field"))   # exploring, not deriving

        sl.forget_reads()

        with sp.track_run():                    # no parents from the loop above
            ...
        ```
    """
    _clear_reads()


def pending_reads() -> list:
    """The runs whose data this session has read, and would record as parents.

    Returns:
        list[dict]: `{"uuid", "name", "items"}` per run read so far.
    """
    return _reads()


__all__ = [
    "Project",
    "load_project",
    "open_project",
    "list_projects",
    "Run",
    "RunCollection",
    "delete_run",
    "forget_reads",
    "pending_reads",
]
