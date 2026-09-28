import argparse
import sys
from pathlib import Path

from silloncore.project_paths import resolve_engine, resolve_storage_root
from silloncore.engine import get_project_summary
from silloncore.display import print_landing, print_landing_outside_project
import silloncli.commands.show as show
import silloncli.commands.add as add
import silloncli.commands.list as list_cmd
import silloncli.commands.query as query
import silloncli.commands.fetch as fetch
import silloncli.commands.prune as prune
import silloncli.commands.report as report
import silloncli.commands.delete as delete
import silloncli.commands.rename as rename
import silloncli.commands.trace as trace
import silloncli.commands.lineage as lineage
import silloncli.commands.projects as projects
import silloncli.commands.versions as versions
import silloncli.commands.diff as diff
import silloncli.commands.like as like

from silloncommon import __version__


'''
This is the lookup table containing all the command that the cli can run. It is use to call
the command themselves but also to initialize their parser.
'''
COMMAND_LIST = {
    "show": show,
    "add": add,
    "list": list_cmd,
    "query": query,
    "fetch": fetch,
    "prune": prune,
    "report": report,
    "delete": delete,
    "rename": rename,
    "trace": trace,
    "lineage": lineage,
    "projects": projects,
    "versions": versions,
    "diff": diff,
    "like": like,
}


# Commands that answer questions about the machine rather than about one
# project, and so must work from any directory.
PROJECT_INDEPENDENT = {"projects"}


def command_launcher(engine, storage_root, args):
    """
    Will take the sql engine and a command and launch the appropriate command from the lookuptable.
    Args:
        engine: The sql engine to read the database at .sillon
        storage_root: The project storage root holding glob/artifact/figure data
        args: The parsed argument for the command
    """
    command_name = args.command
    target_command = COMMAND_LIST.get(command_name)

    if target_command:
        args_dict = vars(args)
        args_dict.pop("command")
        return {command_name: target_command.command(engine, storage_root, args_dict)}

    return {}


def init_parsers(command_subparser):
    """
    Will take the command_subparser of the cli to initialize a parser for each command.
    Each command parser is define in the command script themselves as a add_parser command.
    Args:
        command_subparser: The command subparser created from the parser.
    """
    for key in COMMAND_LIST.keys():
        COMMAND_LIST[key].add_parser(command_subparser)


def cli():
    """
    Cli is the main loop for the command line tool. It will first check if we are in a project_dir
    then it will initialize the parsers and parse the argument to launch the appropriate command.
    Each command is defined in the command folder and contain at list a command function link to
    their name space to launch the command the user want to use and a function add_parser.
    """

    # -- Initialise the parsers (before the project check, so --version /
    #    --help work from anywhere) -- #
    parser = argparse.ArgumentParser(
        prog="sillon",
        description="Git for simulations — explore your logged runs.",
    )
    parser.add_argument(
        "--version", action="version", version=f"sillon {__version__}"
    )
    # Not required: a bare `sillon` falls back to the project overview.
    command_subparser = parser.add_subparsers(dest="command", required=False)
    init_parsers(command_subparser)

    args = parser.parse_args()

    # -- Project-independent commands run before the in-a-project check -- #
    if args.command in PROJECT_INDEPENDENT:
        args_dict = vars(args)
        args_dict.pop("command")
        COMMAND_LIST["projects"].command(None, None, args_dict)
        return

    # -- Getting the Path -- #
    project_dir = Path.cwd()
    if not (project_dir / ".sillon").exists():
        # A bare `sillon` outside a project is still a front door: say what
        # this is and how to find your projects, rather than erroring out.
        if args.command is None:
            print_landing_outside_project(__version__)
            return
        print("Not in a sillon project. Try `sillon projects` to find them.")
        sys.exit(1)

    # -- Getting the engine and storage root (shared with sillonlab) -- #
    engine = resolve_engine(project_dir)
    storage_root = resolve_storage_root(project_dir)

    # -- Bare `sillon`: the project at a glance -- #
    if args.command is None:
        print_landing(
            get_project_summary(engine, storage_root, project_dir), __version__
        )
        return

    command_launcher(engine, storage_root, args)


if __name__ == "__main__":
    cli()
