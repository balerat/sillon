import argparse
import sys
from pathlib import Path

from silloncore.project_paths import resolve_engine, resolve_storage_root
import silloncli.commands.show as show
import silloncli.commands.add as add
import silloncli.commands.context as context
import silloncli.commands.compare as compare
import silloncli.commands.search as search
import silloncli.commands.grab as grab
import silloncli.commands.prune as prune
import silloncli.commands.report as report
import silloncli.commands.delete as delete
import silloncli.commands.rename as rename
import silloncli.commands.whose as whose
import silloncli.commands.lineage as lineage

from silloncommon import __version__


'''
This is the lookup table containing all the command that the cli can run. It is use to call
the command themselves but also to initialize their parser.
'''
COMMAND_LIST = {
    "show": show,
    "add": add,
    "context": context,
    "compare": compare,
    "search": search,
    "grab": grab,
    "prune": prune,
    "report": report,
    "delete": delete,
    "rename": rename,
    "whose": whose,
    "lineage": lineage,
}


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

    # -- Getting the Path -- #
    project_dir = Path.cwd()
    if not (project_dir / ".sillon").exists():
        print("Not in a sillon project.")
        sys.exit(1)

    # -- Getting the engine and storage root (shared with sillonlab) -- #
    engine = resolve_engine(project_dir)
    storage_root = resolve_storage_root(project_dir)

    # -- Execute the command (default to the context overview) -- #
    if args.command is None:
        context.command(engine, storage_root, {"run_name": []})
        return

    command_launcher(engine, storage_root, args)


if __name__ == "__main__":
    cli()
