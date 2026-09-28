import sys
import inspect
import os
import sysconfig

'''
Here are all the function used for extracting metadata linked to python.
'''

def _sillon_package_roots():
    """Directories holding sillon's own source, so we never version ourselves.

    Matters for an editable install: sillon's modules then live outside
    site-packages, so the plain "not a third-party library" filter in
    get_imports() would count them as the user's code — and upgrading sillon
    would flip the code version of every project.
    """
    roots = set()
    for name in ("sillonpy", "silloncommon", "silloncore", "silloncli", "sillonlab"):
        module = sys.modules.get(name)
        path = getattr(module, "__file__", None)
        if path:
            roots.add(os.path.dirname(os.path.abspath(path)))
    return roots


def _stdlib_dirs():
    """Directories holding the standard library, for path-based exclusion."""
    dirs = set()
    for key in ("stdlib", "platstdlib"):
        path = sysconfig.get_paths().get(key)
        if path:
            dirs.add(os.path.abspath(path))
    return dirs


def get_imports():
    '''
    This function will get all the imports used in a python script and sort them between user imports and system imports and also will differentiate
    if an import is a library or a script made by the user.
    '''
    custom_modules = []
    stdlib = sys.stdlib_module_names
    stdlib_dirs = _stdlib_dirs()

    for name, mod in list(sys.modules.items()):
        path = getattr(mod, "__file__", None)

        if path == None:
            continue
        path = os.path.abspath(path)

        # Compare the TOP-LEVEL name: sys.stdlib_module_names holds "asyncio",
        # never "asyncio.base_events", so matching the full dotted name let every
        # stdlib submodule through and reported it as the user's own code.
        if name.split(".")[0] in stdlib:
            continue
        # Belt and braces: anything living under the stdlib directories, which
        # also covers vendored modules whose names are not in the list.
        if any(path.startswith(d + os.sep) for d in stdlib_dirs):
            continue
        if "site-packages" in path or "dist-packages" in path:
            continue
        # Nor is sillon itself. Normally it sits in site-packages and is caught
        # above, but an editable install puts it on a plain path where it would
        # otherwise be reported as the user's own code.
        if any(path.startswith(root + os.sep) for root in _sillon_package_roots()):
            continue
        if not os.path.isfile(path):
            continue

        custom_modules.append(path) # If the module is a users script add it to the custom module list

    return sorted(set(custom_modules)), list(sys.modules.keys()) # Add also the lis of all imported modules

def save_custom_sources(custom_modules):
    '''
    Get the source code of each user imports
    '''
    saved = {}
    for path in custom_modules:
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved[path] = f.read()
        except(OSError, UnicodeDecodeError):
            # Add something to the logging system for the future
            continue
    return saved

def get_main_script():
    '''
    Get the location of the main script
    '''
    main_mod = sys.modules.get('__main__')
    if main_mod and hasattr(main_mod, '__file__'):
        return os.path.abspath(main_mod.__file__)
    return None

def load_main_script_source(script_path):
    if script_path and os.path.exists(script_path):
        with open(script_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Source code not found."

def get_user_script_path():
    """
    Resolve the path of the user's entry script.

    Prefers the canonical `__main__.__file__` (correct for `python myscript.py`),
    and only falls back to walking the call stack when `__main__` has no file
    (e.g. an interactive session) to find the first frame that is not part of
    sillonpy/silloncommon, pytest, or a built-in runner.
    """
    main_script = get_main_script()
    if main_script:
        return main_script

    for frame_info in inspect.stack():
        filename = frame_info.filename

        # Skip the internal libraries
        if "sillonpy" in filename or "silloncommon" in filename:
            continue

        # Skip pytest or built-in python runners
        if "pytest" in filename or filename.startswith("<"):
            continue

        # We found the first file that belongs to the user!
        return os.path.abspath(filename)

    return None  # Fallback if we can't find it


# ==========================================
#              CODE VERSIONING
# ==========================================
#
# A run's "code version" covers the entry script *and* the user's own modules,
# so editing your own library counts as a code change. The hashing itself lives
# in silloncommon.codeversion; this half is about deciding which files belong
# and what to call them.


def _module_key(path, project_path=None):
    """A name for a source file that is stable across machines.

    Absolute paths differ per machine and break when a project moves, so they
    cannot identify a file. Preference order:

    1. relative to the project root, when the file lives inside it;
    2. relative to its own package root — walking up while `__init__.py`
       exists — so an installed library reads as `lattice/ham.py`;
    3. the bare filename.
    """
    path = os.path.abspath(path)

    if project_path:
        try:
            return os.path.relpath(path, os.path.abspath(project_path)).replace(os.sep, "/")
        except ValueError:
            pass  # different drive on Windows

    parts = [os.path.basename(path)]
    directory = os.path.dirname(path)
    while os.path.isfile(os.path.join(directory, "__init__.py")):
        parts.insert(0, os.path.basename(directory))
        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent
    return "/".join(parts)


def collect_code_sources(main_script_path, project_path=None):
    """The sources that make up this run's code version.

    Returns:
        dict: `{stable name: source text}` for the entry script plus every
            module of the user's own that is currently imported.

    Only modules imported by the time this runs are visible — `get_imports()`
    walks `sys.modules` — so something imported lazily inside a function later
    on is missed. Documented rather than papered over.
    """
    custom_modules, _ = get_imports()
    excluded = _sillon_package_roots()

    paths = []
    if main_script_path and os.path.isfile(main_script_path):
        paths.append(os.path.abspath(main_script_path))

    for path in custom_modules:
        path = os.path.abspath(path)
        if any(path.startswith(root + os.sep) or path == root for root in excluded):
            continue
        if path not in paths:  # the entry script is also in sys.modules['__main__']
            paths.append(path)

    sources = {}
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as f:
                sources[_module_key(path, project_path)] = f.read()
        except (OSError, UnicodeDecodeError):
            continue
    return sources
