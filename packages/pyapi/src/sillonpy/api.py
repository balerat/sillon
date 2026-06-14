"""
The API exposes the main tracking functions to the user. 

These functions are loaded through the `simplypy` import. The user should not have 
access to the underlying data logging and server transmission logic. To achieve 
this, a unique `Tracker` object for each simulation run is maintained using a 
`ContextVar`. This shared context allows the API functions to access the tracker 
from anywhere in the user's codebase without passing it explicitly.
"""

from functools import wraps
import time
from contextvars import ContextVar
import atexit
import inspect
from pathlib import Path
from typing import Any, Optional, Dict, Union

from .tracker import Tracker


####################
#     Context      #
####################

# This file will be imported with simply so the context is created here.
_context = ContextVar("simulation_tracker_context", default=None)


def get_context():
    """Fetches the current simulation tracker context.

    Raises:
        RuntimeError: If the tracker context has not been initialized.

    Returns:
        Tracker: The active Tracker instance.
    """
    try:
        return _context.get()
    except LookupError:
        raise RuntimeError("Tracker has not been initialized !")


def set_context(ctx):
    """Updates the active simulation tracker context.

    Args:
        ctx (Tracker | None): The Tracker instance to set as the active context.
    """
    _context.set(ctx)


def _finalize():
    """Atexit hook to cleanly close the connection to the server.

    Ensures that when the run is finished or the script exits, the context's 
    `close` method is called to safely flush data and cut the connection.
    """
    cx = get_context()
    if cx is not None:
        cx.close()


atexit.register(_finalize)  # Closing the connection at exit of the program


####################
#        API       #
####################

def init(
    run_name: Optional[str] = None,
    organisation: Optional[str] = None,
    author: Optional[str] = None,
    project_name: Optional[str] = None,
    project_path: Optional[Union[str, Path]] = None,
):
    """Initializes the Tracker for the current script.

    Instantiates a background tracker linked to a specific project and run name.
    If a context already exists, this function will safely do nothing.

    Args:
        run_name (str, optional): The name of the specific simulation run. Defaults to None.
        organisation (str, optional): The name of the organization. Defaults to None.
        author (str, optional): The name of the person running the simulation. Defaults to None.
        project_name (str, optional): The project grouping this simulation belongs to. Defaults to None.
        project_path (str | Path, optional): The absolute or relative path to the project root. Defaults to None.
    """
    if get_context() is None:
        simulation_tracker = Tracker(
            run_name=run_name,
            project_name=project_name,
            project_path=project_path,
            organisation=organisation,
            author=author,
        )
        set_context(simulation_tracker)


def track(
    func=None,
    *,
    save_result: bool = False,
    run_name: Optional[str] = None,
    organisation: Optional[str] = None,
    author: Optional[str] = None,
    project_name: Optional[str] = None,
    project_path: Optional[Union[str, Path]] = None,
):
    """Decorator to log function execution and optionally initialize the Tracker.

    Automatically logs the function's arguments, keyword arguments, execution 
    duration, and return value. It can be used with or without arguments 
    (e.g., `@track` or `@track(save_result=True)`).

    Args:
        func (callable, optional): The function being decorated.
        save_result (bool): Whether to explicitly save the function's return value to the HDF5 glob. Defaults to False.
        run_name (str, optional): Optional initialization parameter.
        organisation (str, optional): Optional initialization parameter.
        author (str, optional): Optional initialization parameter.
        project_name (str, optional): Optional initialization parameter.
        project_path (str | Path, optional): Optional initialization parameter.

    Returns:
        callable: The wrapped function.
    """
    if func is None:
        def decorator(f):
            return track(
                f,
                save_result=save_result,
                run_name=run_name,
                organisation=organisation,
                author=author,
                project_name=project_name,
                project_path=project_path,
            )

        return decorator

    @wraps(func)
    def wrapper(*args, **kwargs):
        # 1. Initialize Context if it doesn't exist
        if get_context() is None:
            init(
                run_name=run_name,
                organisation=organisation,
                author=author,
                project_name=project_name,
                project_path=project_path,
            )

        # 2. Execute the function
        func_id = str(func.__name__)
        start_time = time.time()

        function_result = func(*args, **kwargs)

        end_time = time.time()

        # 3. Log everything
        log_param("sillon.python.tracked_function_args." + func_id, args)
        log_param("sillon.python.tracked_function_kwargs." + func_id, kwargs)
        _add_callstack(func_id)

        add_metadata(
            "sillon.python.tracked_function_metadata." + func_id,
            {
                "start_time": start_time,
                "end_time": end_time,
                "duration": end_time - start_time,
                "name": func_id,
            },
        )

        if function_result is not None:
            log_result(
                "sillon.python.tracked_function_result." + func_id,
                function_result,
                save_result=save_result,
            )

        return function_result

    return wrapper


def _add_callstack(func_id: str):
    """Adds a function call to the tracker's call stack.

    Args:
        func_id (str): The name or identifier of the tracked function.
    """
    ctx = get_context()
    ctx.add_callstack(func_id)


def log_param(
    key_or_dict: Optional[Union[str, Dict[str, Any]]] = None,
    value: Optional[Any] = None,
    **kwargs,
):
    """Logs parameters to the current simulation context.

    Provides a highly flexible interface allowing users to pass parameters as 
    a single key/value pair, a dictionary, or direct keyword arguments.

    Args:
        key_or_dict (str | dict, optional): The parameter key string, or a dictionary of parameters. Defaults to None.
        value (Any, optional): The parameter value if `key_or_dict` is a string. Defaults to None.
        **kwargs: Additional parameters passed as keyword arguments.

    Raises:
        ValueError: If a string key is provided without a value, or if no valid data is provided at all.
    """
    ctx = get_context()

    # CASE 1: The user passed a string key and a value
    if isinstance(key_or_dict, str):
        if value is None:
            raise ValueError(
                f"You provided a parameter name '{key_or_dict}' but no value."
            )
        ctx.log_param(key_or_dict, value)

    # CASE 2: The user passed a dictionary
    elif isinstance(key_or_dict, dict):
        for k, v in key_or_dict.items():
            ctx.log_param(k, v)

    # CASE 3: The user passed kwargs
    if kwargs:
        for k, v in kwargs.items():
            ctx.log_param(k, v)

    # ERROR CHECK: Did they pass absolutely nothing?
    if key_or_dict is None and not kwargs:
        raise ValueError(
            "Invalid Entry: You must provide a key/value pair, a dictionary, or keyword arguments."
        )


def log_result(
    id: Optional[Union[str, Dict[str, Any]]] = None,
    value: Optional[Any] = None,
    path: Optional[Union[str, Path]] = None,
    save_result: bool = True,
    **kwargs,
):
    """Logs an output result, metric dictionary, or physical file artifact.

    If `save_result` is True and a `path` is given, it copies the file to the 
    artifact storage. If `save_result` is True for a dict or key/value pair, 
    it adds the heavy data to the HDF5 glob. Both cases log a pointer in the database.

    Args:
        id (str | dict, optional): The identifier string, or a dictionary of results. Defaults to None.
        value (Any, optional): The data value to store. Defaults to None.
        path (str | Path, optional): The file path to an artifact. Defaults to None.
        save_result (bool): Whether to physically save the artifact/data or just log the pointer. Defaults to True.
        **kwargs: Additional results passed as keyword arguments.

    Raises:
        ValueError: If both a `value` and a `path` are provided simultaneously.
        ValueError: If neither a value, path, dictionary, nor kwargs are provided.
        ValueError: If the `id` format is inherently invalid.
    """
    ctx = get_context()

    # 1. ERROR CHECK: Ambiguous input
    if value is not None and path is not None:
        raise ValueError(
            "Ambiguous input: You cannot provide both a 'value' and a 'path' at the same time."
        )

    # 2. ERROR CHECK: Missing data
    if value is None and path is None and not isinstance(id, dict) and not kwargs:
        raise ValueError(
            "Missing data: You must provide a 'value', a 'path', or a dictionary of results."
        )

    # 3. CASE: Dictionary of results
    if isinstance(id, dict):
        for k, v in id.items():
            ctx.log_result(k, {"value": v, "path": None, "save_result": save_result})
        return  # Exit early

    # 4. CASE: A file path is provided
    if path is not None:
        file_path = Path(path)
        # If the user didn't provide a string ID, automatically use the file name
        result_id = id if isinstance(id, str) else file_path.name

        ctx.log_result(
            result_id,
            {"value": None, "path": str(file_path), "save_result": save_result},
        )
        return

    # 5. CASE: A standard single value is provided
    if isinstance(id, str) and value is not None:
        ctx.log_result(id, {"value": value, "path": None, "save_result": save_result})
        return

    # 6. CASE: Kwargs are provided
    if kwargs:
        for k, v in kwargs.items():
            ctx.log_result(k, {"value": v, "path": None, "save_result": save_result})

    # Catch-all for weird edge cases
    else:
        raise ValueError(
            "Invalid input format. The 'id' must be a string or a dictionary."
        )


_figure_counter = {"count": 0}


def log_figure(
    figure: Optional[Any] = None,
    name: Optional[str] = None,
    path: Optional[Union[str, Path]] = None,
    used: Optional[Union[str, list]] = None,
    caption: Optional[str] = None,
    **info,
):
    """Logs a figure produced during the run, with its data provenance.

    The figure is stored alongside the run (hashed, like an artifact) in a
    dedicated figure table. The `used` argument is the provenance link: list
    there the names of the parameters and results the figure was built from,
    so anyone exploring the run later can see exactly what data was used for
    what figure.

    Example:
        ```python
        fig, ax = plt.subplots()
        ax.plot(super_param, coef)
        sl.log_figure(fig, name="fit", used=["super_param", "coef"],
                      caption="Linear fit of the polynomial")
        ```

    Args:
        figure (Any, optional): A live figure object exposing `savefig`
            (matplotlib Figure) or `get_figure` (matplotlib Axes). Rendered
            to png automatically. Defaults to None.
        name (str, optional): The figure name. Defaults to the figure label,
            the file name, or an auto-numbered name.
        path (str | Path, optional): The path of an already rendered figure
            file, as an alternative to `figure`. Defaults to None.
        used (str | list, optional): The parameter/result names the figure
            was built from. Defaults to None.
        caption (str, optional): A short description of the figure.
        **info: Any extra metadata to attach to the figure.

    Raises:
        ValueError: If neither or both of `figure` and `path` are provided.
    """
    ctx = get_context()

    if figure is None and path is None:
        raise ValueError("You must provide a 'figure' object or a 'path'.")
    if figure is not None and path is not None:
        raise ValueError(
            "Ambiguous input: You cannot provide both a 'figure' and a 'path'."
        )

    # A matplotlib Axes is accepted and resolved to its parent Figure
    if figure is not None and not hasattr(figure, "savefig"):
        if hasattr(figure, "get_figure"):
            figure = figure.get_figure()
        else:
            raise ValueError("The 'figure' object must expose savefig().")

    # Resolve the figure name
    if name is None:
        label = figure.get_label() if hasattr(figure, "get_label") else ""
        if label:
            name = label
        elif path is not None:
            name = Path(path).stem
        else:
            _figure_counter["count"] += 1
            name = f"figure_{_figure_counter['count']}"

    if isinstance(used, str):
        used = [used]

    meta = {"used": list(used or [])}
    if caption is not None:
        meta["caption"] = caption
    meta.update(info)

    ctx.log_figure(name, figure=figure, path=path, meta=meta)


def add_metadata(
    key_or_dict: Optional[Union[str, Dict[str, Any]]] = None,
    metadata: Optional[Any] = None,
):
    """Logs custom user metadata to the simulation context.

    Automatically prefixes all keys with `sillon.user_metadata.` so they can
    be cleanly segregated and retrieved later without overlapping with system keys.

    Args:
        key_or_dict (str | dict, optional): The metadata key string, or a dictionary of metadata. Defaults to None.
        metadata (Any, optional): The metadata value if `key_or_dict` is a string. Defaults to None.

    Raises:
        ValueError: If a string key is provided without a corresponding value.
    """
    ctx = get_context()
    
    # CASE 1: The user passed a string key and a value
    if isinstance(key_or_dict, str):
        if metadata is None:
            raise ValueError(
                f"You provided a parameter name '{key_or_dict}' but no value."
            )
        ctx.add_metadata("sillon.user_metadata." + key_or_dict, metadata)

    # CASE 2: The user passed a dictionary
    elif isinstance(key_or_dict, dict):
        for k, v in key_or_dict.items():
            ctx.add_metadata("sillon.user_metadata." + k, v)


def add_note(note: Union[str, list]):
    """Appends a textual note (or list of notes) to the current simulation.

    Args:
        note (str | list[str]): A single string note or a list of string notes.

    Raises:
        ValueError: If the provided note is not a string or a list of strings.
    """
    if isinstance(note, str) or (
        isinstance(note, list) and all(isinstance(x, str) for x in note)
    ):
        ctx = get_context()
        ctx.add_note(note)
    else:
        raise ValueError("Note must be of type str")


def add_tag(tag: Union[str, list]):
    """Appends a tag (or list of tags) to the current simulation.

    Args:
        tag (str | list[str]): A single string tag or a list of string tags.
    """
    if isinstance(tag, str) or (
        isinstance(tag, list) and all(isinstance(x, str) for x in tag)
    ):
        ctx = get_context()
        ctx.add_tag(tag)


def force_dump():
    """Forces the immediate synchronization and closing of the current tracker.

    This explicitly calls the close method on the context to flush all data 
    to the background server and database, and resets the local `ContextVar` to None.
    """
    ctx = get_context()
    ctx.close()
    set_context(None)
