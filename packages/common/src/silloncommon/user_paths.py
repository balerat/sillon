"""Per-user (not per-project) locations sillon writes to.

Only the global project registry lives here; everything else is inside the
project's own `.sillon/` directory.
"""

import os
import sys

from pathlib import Path


def user_config_dir() -> Path:
    """Directory for sillon's user-level configuration.

    POSIX behaviour is unchanged (`~/.config/sillon`, honouring XDG_CONFIG_HOME)
    so existing installs keep their registry exactly where it is. Windows gets
    `%APPDATA%\\sillon` instead of a stray `~/.config`, which is where a Windows
    user would expect it.
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "sillon"
        return Path.home() / "AppData" / "Roaming" / "sillon"

    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "sillon"
    return Path.home() / ".config" / "sillon"
