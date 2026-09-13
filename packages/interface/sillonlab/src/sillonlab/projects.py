"""Machine-wide project discovery — the notebook counterpart of `sillon projects`.

`project.py` is about *one* loaded project; this module is about finding which
projects exist on this machine in the first place, so you can open one without
remembering where you put it.

Both this and the CLI read the same records from `silloncore.projects`, so they
never disagree.
"""

from silloncore.projects import find_project, get_projects

from sillonlab.project import Project, load_project


def list_projects(with_stats: bool = True, include_missing: bool = True) -> list:
    """Every sillon project registered on this machine.

    Example:
        ```python
        import sillonlab as sl

        for p in sl.list_projects():
            print(p["project_name"], p["run_count"], p["project_path"])
        ```

    Args:
        with_stats (bool): Include `run_count` and `last_activity`, which means
            opening each project's database. False for a fast listing.
        include_missing (bool): Keep projects whose directory is gone, flagged
            `exists=False`, rather than hiding them — an unmounted drive should
            look different from a project you never had.

    Returns:
        list[dict]: `project_name`, `project_path`, `project_storage`, `exists`,
            and when `with_stats`, `run_count`, `last_activity`, `readable`.
    """
    return get_projects(include_missing=include_missing, with_stats=with_stats)


def open_project(name_or_path: str) -> Project:
    """Load a project by its registered name instead of by path.

    Accepts a project name (case-insensitive; a unique prefix is enough) or a
    path, so the output of `list_projects` can be used directly.

    Example:
        ```python
        project = sl.open_project("Shaking Lattice")
        ```

    Args:
        name_or_path (str): A registered project name, or a path.

    Raises:
        LookupError: If nothing matches, or if a name prefix is ambiguous.

    Returns:
        Project: The loaded project.
    """
    record = find_project(name_or_path)
    if record is None:
        raise LookupError(
            f"No registered project matches '{name_or_path}'. "
            "Use sillonlab.list_projects() to see what is registered "
            "(a name must be unique, or give the path instead)."
        )
    return load_project(record["project_path"])
