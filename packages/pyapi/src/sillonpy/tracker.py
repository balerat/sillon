import uuid
from pathlib import Path
import os
import sys
import time

from .serverCom import ServerCom
from .metadata import get_imports, save_custom_sources, load_main_script_source, get_user_script_path
from silloncommon.commands import (
    LogResultCmd,
    LogFigureCmd,
    LogParamCmd,
    AddMetaDataCmd,
    AddNoteCmd,
    AddTagCmd,
)
from silloncommon.hdf5_staging import is_large_array, write_staging_array

"""
Here is the definition of the Tracker object.
"""


class Tracker:
    """
    The tracker is the mirror on the client side of the simulation object on the server. Its
    tasks during the run of the simulation is to send command to the server from run specific
    command to user entered command via the api. It will start a connection to the server
    thanks to the ServerCom object and then will expose its method to the api for the user to
    use. It will also log some sillon specific metadata on the run and send it to the server.
    (Like what language is used, where is the simulation launch, a profiler)
    """

    def __init__(
        self,
        run_name=None,
        project_name=None,
        organisation=None,
        author=None,
        project_path=None,
    ):

        # Name the project and get its path and assign the uuid
        self.run_name = run_name
        if project_path is None:
            project_path = os.getcwd()
        self.project_path = Path(project_path).resolve()
        self.project_name = project_name
        self.organisation = organisation
        self.author = author
        self.platform = "python"
        self.uuid = uuid.uuid4()  # Will need to change to uuid7 in the future
        self.main_script_path = get_user_script_path()
        # Launch the server
        self.server = ServerCom(
            str(self.uuid),
            self.run_name,
            self.project_name,
            self.platform,
            self.organisation,
            self.author,
            self.project_path,
        )
        self.server.connect_server()
        self.cwd = os.getcwd()
        self.callstack = {}
        # None until something claims an outcome. close() only reports a status
        # when this is set; otherwise the server's default promotion applies.
        self.status = None
        self._install_excepthook()
        self.metadata_pysillon()

    def _install_excepthook(self):
        """Notice an unhandled exception so the run is not sealed as a success.

        close() runs from an atexit hook, and atexit fires on a normal exit and
        on a crash alike -- so without this the tracker cannot tell them apart
        and a simulation that died is recorded as SUCCESS. sys.excepthook is the
        only place a script-level unhandled exception is observable
        (sys.last_value is set by the interactive interpreter, not by scripts).

        The previous hook is kept and still called, so tracebacks print exactly
        as before and any other library's hook keeps working.
        """
        previous_hook = sys.excepthook

        def sillon_excepthook(exc_type, exc_value, exc_tb):
            self.mark_failed(exc_type, exc_value)
            previous_hook(exc_type, exc_value, exc_tb)

        sys.excepthook = sillon_excepthook

    def mark_failed(self, exc_type, exc_value):
        """Record that this run died, and why.

        Idempotent, and deliberately never raises: it runs on the crash path,
        where a second failure would bury the user's real traceback under ours.
        """
        if self.status is not None:
            return
        self.status = "CRASHED"
        try:
            self.add_metadata(
                "sillon.error.type", getattr(exc_type, "__name__", str(exc_type))
            )
            self.add_metadata("sillon.error.message", str(exc_value))
        except Exception:
            pass

    def metadata_pysillon(self):
        """
        Send some basic metadata at every run
        """
        custom_modules, sys_modules = get_imports()
        self.start_time = time.time()
        self.metadata = {
            "sillon.language": "python",
            "sillon.python.cwd": self.cwd,
            "sillon.main_script_source": load_main_script_source(self.main_script_path),
            "sillon.python.custom_modules": custom_modules,
            # "sillon.python.sys_modules": sys_modules,
            # "sillon.python.source_custom_modules": save_custom_sources(custom_modules), Need to implement a clever way of sending that to the server.
        }
        for key, value in self.metadata.items():
            self.add_metadata(key, value)


    def close(self):
        """
        Method that will be launched when the run is ended. It will save the profiler data and get the runtime. It will also close the connection to the server.
        """
        self.run_time = time.time() - self.start_time
        self.add_metadata("sillon.runtime", self.run_time)
        # Report the outcome explicitly. The server only promotes a run to
        # SUCCESS while its status is still RUNNING, so sending CRASHED here
        # stops a failed run being sealed as a successful one.
        if self.status is not None:
            self.add_metadata("sillon.status", self.status)

        self.add_metadata("sillon.python.callstack", self.callstack)
        self.server.dump_run()  # When the simulation ends we ask the server to dump the simulation into the database

    """
    Here are all the method exposed to the API. They are not redoundant. The goal of the api is to use the contextVar object to call form 
    function call the same tracker object in every part of the code of a run. They thus all point to these method of the tracker object.
    """

    def add_callstack(self, func_id):
        try:
            self.callstack[func_id] += 1
        except:
            self.callstack[func_id] = 1

    def log_param(self, id, parameter):
        # Offload heavy parameter arrays to a staging file (claimed into the
        # glob by the server), the same way large results are handled.
        if is_large_array(parameter):
            # Send the staging reference as-is, exactly like log_result. Wrapping
            # it in a second envelope loses the shape/dtype the server records
            # and hides staging_path where the server does not look for it.
            parameter = write_staging_array(parameter, self.project_path)
        self.server.execute_command(LogParamCmd(id, parameter))

    def log_result(self, id, result):
        value = result.get("value")
        if value is not None and is_large_array(value):
            pointer = write_staging_array(value, self.project_path) 
            result = {**result, "value": pointer}
        self.server.execute_command(LogResultCmd(id, result))

    def log_figure(self, id, figure=None, path=None, meta=None):
        """
        Send a figure to the server. A live figure object (matplotlib) is rendered to a
        temporary png in the project staging directory and the server claims (and deletes)
        it; an already rendered file given by path is copied without cleanup.
        """
        meta = dict(meta or {})

        if figure is not None:
            staging_dir = self.project_path / ".sillon" / "staging"
            staging_dir.mkdir(parents=True, exist_ok=True)
            figure_path = staging_dir / f"{uuid.uuid4().hex}.png"
            figure.savefig(figure_path)
            meta.setdefault("format", "png")
            payload = {"path": str(figure_path), "meta": meta, "cleanup": True}
        else:
            figure_path = Path(path).resolve()
            meta.setdefault("format", figure_path.suffix.lstrip("."))
            payload = {"path": str(figure_path), "meta": meta, "cleanup": False}

        self.server.execute_command(LogFigureCmd(id, payload))

    def add_metadata(self, id, metadata):
        self.server.execute_command(AddMetaDataCmd(id, metadata))

    def add_note(self, note):
        self.server.execute_command(AddNoteCmd("", note))

    def add_tag(self, tag):
        self.server.execute_command(AddTagCmd(tag, tag))
