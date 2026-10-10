import os
import pathlib
import shutil
import stat
from pathlib import Path
import uuid
import toml

from sqlmodel import SQLModel, Session

from silloncommon.database import insert_simulation, create_default_engine_root
from silloncore.projects import create_project
from silloncommon import project_config, registry
from .glob import Glob, get_hash

# .sillon file structure
# .sillon /
#           config.json
#           database.sql
#           artifact /
#                   uuid /
#                   ...
#           glob /
#                   uuid /
#                   ...
# The machine-wide project registry lives in silloncommon.registry, which
# resolves the right per-OS config location and owns the file format.


class ProjectEnvironmentHandler:
    """Manages the workspace environment for a sillon project.

    This class handles the initialization and management of the `.sillon` 
    directory, including the SQLite database, configuration files, and 
    artifact/glob structures required for a project.

    Attributes:
        db_path (Path): The file path to the SQLite database.
        sillon_dir (Path): The file path to the `.sillon` directory.
    """

    def __init__(self,project_path, project_name=None, project_storage_root=None):
        """Initializes the project environment handler.

        Args:
            project_name (str): The name of the project.
            project_path (str | Path): The directory path where the project resides.
            project_storage_root (str | Path, optional): Where heavy data
                should live, for a project being created here.
        """
        self._project_path = pathlib.Path(project_path).expanduser().resolve()
        # The directory, config, database and registry entry come from the one
        # shared implementation, so a project the daemon brings into existence
        # is identical to one `sillon init` made. This is what keeps
        # zero-config logging working: the first run still creates the project.
        info = create_project(
            self._project_path,
            project_name=project_name,
            storage_root=project_storage_root,
        )
        self._project_id = info["project_id"]
        self._project_name = info["project_name"]
        self._storage_root = info["storage_root"]
        self._sillon_dir = self._project_path / ".sillon"
        self._config_path = self._sillon_dir / "config.toml"
        self._learn_project_name(project_name)
        self._create_sql_engine()

    def _learn_project_name(self, project_name):
        """Record a name supplied by a run when the project had none.

        A project created by `sp.init()` with no `project_name=`, and then run
        again with one, should pick it up -- the alternative is a project that
        stays nameless forever because of how its first run was written.
        """
        if not project_name or self._project_name:
            return
        config = project_config.read_config(self._project_path)
        config.setdefault("Environment", {})["project_name"] = project_name
        project_config.write_config(self._project_path, config)
        self._project_name = project_name
        try:
            registry.upsert(
                self._project_id, self._project_path, project_name,
                self._sillon_dir, self._storage_root,
            )
        except Exception:
            pass
        

    def _create_sql_engine(self):
        self._engine = create_default_engine_root(self._storage_root)
        SQLModel.metadata.create_all(self._engine)
        self._sql_session = Session(self._engine)
        self._db_path = self._storage_root / Path("database.sql")

    def get_config(self):
        """Retrieves the current project configuration.

        Returns:
            dict: The configuration dictionary loaded from `config.toml`.
        """
        return self._config

    def get_engine(self):
        """Retrieves the SQLAlchemy engine linked to the project database.

        Returns:
            Engine: The active SQLAlchemy engine instance.
        """
        return self._engine

    def get_sql_session(self):
        """Retrieves the active database session.

        Returns:
            Session: The SQLModel session for database interactions.
        """
        return self._sql_session

    def get_project_path(self):
        """Retrieves the base path of the project.

        Returns:
            Path: The resolved path to the project root.
        """
        return self._project_path

    def commit_run(self, run):
        """Saves a simulation run to the database and HDF5 glob.

        Commits the HDF5 heavy results, closes the glob file safely, 
        and inserts the structured simulation record into the SQLite database.

        Args:
            run: The simulation run object containing tracking data and a `.glob` instance.

        Returns:
            int: The database ID of the inserted simulation record.
        """
        run.glob.commit_result()
        run.glob.commit_parameter()
        run.glob.close()
        try:
            table = insert_simulation(run, self._sql_session)
            self._sql_session.commit()
            self._sql_session.refresh(table)
            return table.id
        except Exception:
            # One Session serves every run for the daemon's whole life, so a
            # failed commit left un-rolled-back puts it in a failed-transaction
            # state and every *later* run raises PendingRollbackError. One bad
            # run must not take the rest of the session down with it.
            self._sql_session.rollback()
            raise

    def _change_config(self, **kwargs):
        for key, item in kwargs.items():
            old_item = self._config.get(key)
            if old_item:
               self._config[key] = item
        with open(self._config_path, "w", encoding="utf-8") as f:
            toml.dump(self._config, f)

class RunEnvironmentHandler:
    """Manages the file storage structure for an individual simulation run.

    This class isolates artifacts and glob (HDF5) files for a specific run 
    based on its unique UUID, ensuring isolated storage per run.

    Attributes:
        uuid (str): The unique identifier for the run.
        project_path (Path): The root path of the parent project.
        artifact_path (Path): The specific folder path for this run's artifacts.
        glob_path (Path): The specific folder path for this run's HDF5 glob file.
    """
    def __init__(self, uuid, project_path):
        """Initializes the environment handler for a specific run.

        Args:
            uuid (str): The unique identifier representing this simulation run.
            project_path (str | Path): The base directory of the parent project.
        """
        self.uuid = uuid
        self.project_path = pathlib.Path(project_path)
        # Same resolver as the readers use, so a run's data lands where
        # `sillon` and `sillonlab` will later look for it.
        self.storage_root = project_config.resolve_storage_root(self.project_path)

        self.artifact_path = self.storage_root / "artifact" / f"{self.uuid}"
        self.glob_path = self.storage_root / "glob" / f"{self.uuid}"

        try:
            os.makedirs(self.artifact_path, exist_ok=True)
            os.makedirs(self.glob_path, exist_ok=True)
        except Exception as e:
            raise ConnectionError(f"Impossible to create storage dir: {e}")

    def create_glob(self):
        """Creates and returns an HDF5 Glob interface for this run.

        Returns:
            Glob: An initialized Glob instance pointing to the run's specific `glob_path`.
        """
        return Glob(self.glob_path)

    def save_figure(self, file_path):
        """Copies a rendered figure file into the run's figure storage.

        Mirrors `save_artifact` but targets the `figure` directory, keeping
        tracked figures separate from generic artifacts.

        Args:
            file_path (str | Path): The path to the rendered figure file.

        Raises:
            FileNotFoundError: If the provided `file_path` does not exist.

        Returns:
            tuple: A tuple containing:
                - str: The figure storage pointer (folder uuid).
                - str: The calculated hash of the figure file.
        """
        src_path = Path(file_path)
        if not src_path.exists():
            raise FileNotFoundError(f"{file_path} does not exist")

        hsh = get_hash(str(src_path))
        figure_id = uuid.uuid4()

        figure_dir = self.storage_root / "figure" / f"{self.uuid}" / str(figure_id)
        os.makedirs(figure_dir)
        shutil.copy(src_path, figure_dir)

        return str(figure_id), hsh

    def save_artifact(self, file_path):
        """Copies an artifact (file or directory) into the run's artifact storage.

        Calculates the hash of the source file, generates a new UUID for the 
        artifact folder, and securely copies the content into the `.sillon/artifact` 
        directory.

        Args:
            file_path (str | Path): The path to the source file or directory to be saved.

        Raises:
            FileNotFoundError: If the provided `file_path` does not exist on disk.

        Returns:
            tuple: A tuple containing:
                - str: The absolute path to the newly saved artifact directory.
                - str: The calculated hash of the source artifact.
        """
        src_path = Path(file_path)
        hsh = get_hash(file_path)
        artifact_id = uuid.uuid4()
        
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"{file_path} does not exist")
            
        os.makedirs(self.artifact_path / str(artifact_id))
        
        if src_path.is_file():
            shutil.copy(src_path, self.artifact_path / str(artifact_id))
        elif src_path.is_dir():
            destination_folder = self.artifact_path / str(artifact_id) / src_path.name

            if destination_folder.exists():
                shutil.rmtree(destination_folder)

            shutil.copytree(src_path, destination_folder)
            
        return str(artifact_id), hsh
