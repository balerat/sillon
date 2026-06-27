import os
import pathlib
import shutil
import stat
from pathlib import Path
import uuid
import toml

from sqlmodel import SQLModel, Session

from silloncommon.database import insert_simulation, create_default_engine_root
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
PROJECT_LIST = Path("~/.config/sillon/registery.toml").expanduser()


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
        """
        self._project_path = pathlib.Path(project_path)
        self._create_sillon_dir()
        self._project_name = project_name or ""
        self._generate_default_config(project_storage_root)
        self._load_config_file()
        os.makedirs(self._storage_root, exist_ok=True)
        self._create_sql_engine()
        self._raise_permission_sill()
        self._add_project()
        

    def _generate_default_config(self, project_storage_root):
        """Creates a default configuration dictionary for a sillon project.

        Args:
            project_name (str): The name of the project.
            project_uuid (str): The universally unique identifier for the project.

        Returns:
            dict: A dictionary containing the basic configuration keys `project_name` 
                and `project_uuid`.
        """
        self._project_id = uuid.uuid4()  # Will be set or loaded in init_environment
        self._config = {}
        if project_storage_root:
            self._storage_root = project_storage_root / "sillon-storage" /  f"{self._project_id}"
        else:
            self._storage_root = self._sillon_dir
        self._config["Environment"] = {"project_id": str(self._project_id)}
        self._config["storage"] = {"storage_root": str(self._storage_root)}

    def _create_sillon_dir(self):
        self._sillon_dir = self._project_path / ".sillon"
        os.makedirs(self._sillon_dir, exist_ok=True)

    def _load_config_file(self):
        self._config_path = self._sillon_dir / "config.toml"
        if not self._config_path.exists():
            print("creating config at ", self._config_path)
            with open(self._config_path, "w") as f:
                toml.dump(self._config, f)
        else:
            with open(self._config_path, "r") as f:
                self._config = toml.load(f)
                self._project_id = self._config["Environment"]["project_id"]
                self._storage_root = Path(self._config["storage"]["storage_root"])

    def _raise_permission_sill(self):
        # 0o775 adds Write/Execute permissions for the owner and group
        os.chmod(
            self._sillon_dir,
            os.stat(self._db_path).st_mode
            | stat.S_IWUSR
            | stat.S_IXUSR
            | stat.S_IWGRP
            | stat.S_IXGRP,
        )
        # Ensure the file itself is writable
        os.chmod(
            self._db_path, os.stat(self._db_path).st_mode | stat.S_IWUSR | stat.S_IWGRP
        )

    def _create_sql_engine(self):
        self._engine = create_default_engine_root(self._storage_root)
        SQLModel.metadata.create_all(self._engine)
        self._sql_session = Session(self._engine)
        self._db_path = self._storage_root / Path("database.sql")

    def _create_project_list(self):
        os.makedirs(PROJECT_LIST.parent, exist_ok=True)
        with open(PROJECT_LIST, "w") as f:
            toml.dump({"project": {}}, f)

    def _add_project(self):
        if not PROJECT_LIST.exists():
            self._create_project_list()
        with open(PROJECT_LIST, "r") as f:
            data = toml.load(f)
        data.setdefault("project", {})[str(self._project_id)] = {
            "project_name": self._project_name,
            "project_id": str(self._project_id),
            "project_path": str(self._project_path),
            "project_sil": str(self._sillon_dir),
            "project_storage": str(self._storage_root),
        }
        with open(PROJECT_LIST, "w") as f:
            toml.dump(data, f)

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
        table = insert_simulation(run, self._sql_session)
        self._sql_session.commit()
        self._sql_session.refresh(table)
        return table.id

    def _change_config(self, **kwargs):
        for key, item in kwargs.items():
            old_item = self._config.get(key)
            if old_item:
               self._config[key] = item
        with open(self._config_path, "w") as f:
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
    def _load_config(self):
        config = toml.load(self.project_path / ".sillon" / "config.toml")
        return config
    
    def __init__(self, uuid, project_path):
        """Initializes the environment handler for a specific run.

        Args:
            uuid (str): The unique identifier representing this simulation run.
            project_path (str | Path): The base directory of the parent project.
        """
        self.uuid = uuid
        self.project_path = pathlib.Path(project_path)
        config = self._load_config()
        self.storage_root = Path(config["storage"]["storage_root"])
        
        self.artifact_path = self.storage_root / "artifact" / f"{self.uuid}"
        self.glob_path = self.storage_root / "glob" / f"{self.uuid}"

        # self.artifact_path = self.project_path / ".sillon" / "artifact" / f"{self.uuid}"
        # self.glob_path = self.project_path / ".sillon" / "glob" / f"{self.uuid}"
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
