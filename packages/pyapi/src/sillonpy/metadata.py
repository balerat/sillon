import sys
import inspect
import os

'''
Here are all the function used for extracting metadata linked to python.
'''

def get_imports():
    '''
    This function will get all the imports used in a python script and sort them between user imports and system imports and also will differentiate
    if an import is a library or a script made by the user.
    '''
    custom_modules = []
    stdlib = sys.stdlib_module_names # Get all modules in the current script

    for name, mod in sys.modules.items():
        path = getattr(mod, "__file__", None)

        if path == None:
            continue
        path = os.path.abspath(path)
        if name in stdlib or"site-packages" in path or "dist-packages" in path: 
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
