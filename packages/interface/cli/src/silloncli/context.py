"""Where the command is running, as the commands need to see it.

The CLI finds its project by searching upward, so `Path.cwd()` is no longer
the project root — it is wherever you happen to be standing inside one. A
command that needs the root (to read the project's name, or to record where a
bundle came from) asks here rather than assuming.
"""

from pathlib import Path

from silloncommon.project_config import find_project_root

__all__ = ["project_root"]


def project_root() -> Path:
    """The root of the project the command is running in.

    Falls back to the current directory, which only happens for a command
    dispatched outside a project — `main.py` has already refused the rest.
    """
    return find_project_root(Path.cwd()) or Path.cwd()
