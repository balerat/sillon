import uuid
from pathlib import Path
import cProfile
import os
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
        self.start_profiler()
        self.callstack = {}
        self.metadata_pysillon()

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
            "sillon.python.sys_modules": sys_modules,
            # "sillon.python.source_custom_modules": save_custom_sources(custom_modules), Need to implement a clever way of sending that to the server.
        }
        for key, value in self.metadata.items():
            self.add_metadata(key, value)

    def start_profiler(self):
        """
        Start a python profiler  for the run
        """
        try:
            self.profiler = cProfile.Profile()
            self.profiler.enable()
            self.profiler_enabled = True
        except:
            self.profiler_enabled = False

    def close(self):
        """
        Method that will be launched when the run is ended. It will save the profiler data and get the runtime. It will also close the connection to the server.
        """
        self.run_time = time.time() - self.start_time
        self.add_metadata("sillon.runtime", self.run_time)
        self.add_metadata("sillon.status", "SUCCESS")

        if self.profiler_enabled:
            self.profiler.disable()
            self.profiler.dump_stats("profiling.txt")
            self.add_metadata("sillon.python.cprofiler_dump", "profiling.txt")
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
