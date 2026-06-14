from tabulate import tabulate
import argparse

from silloncore.engine import get_run_details

class ShowAction(argparse.Action):
    """
    Define an action to be used for the show command. It will let the user add more argument to the parser
    but wil default to a value if none are provided.
    """

    def __call__(self, parser, namespace, values, option_strings=None):
        """
        The action is used when called by argparse. It is a standard way of creating actions with argparse.
        """
        items = getattr(namespace, self.dest) or []

        if not values:
            items.extend(self.const)
        else:
            items.extend(values)

        setattr(namespace, self.dest, items)


def add_parser(command_subparser):
    # -- Parser for the show command -- #
    show_parser = command_subparser.add_parser("show")
    show_parser.add_argument(
        "run_name",
        nargs="*",
        type=str,
        help="The UUIDs, IDs, or names of the runs",
    )
    show_parser.add_argument(
        "-p",
        "--parameter",
        action=ShowAction,
        nargs="*",
        type=str,
        const=["%all%"],
        default=None,
    )
    show_parser.add_argument(
        "-r",
        "--result",
        action=ShowAction,
        nargs="*",
        type=str,
        const=["%all%"],
        default=None,
    )
    show_parser.add_argument(
        "-m",
        "--metadata",
        action=ShowAction,
        nargs="*",
        type=str,
        const=["%all%"],
        default=None,
    )


def format_pretty(data, type_name: str):
    """
    This function creates a table from the result of the show command except for atifacts.
    """
    # Extract the list from your dictionary
    # rows = data.get('parameter', [])
    headers = ["Run name", "Timestamp", type_name, "Value"]

    # Print a clean, formatted table
    print(tabulate(data, headers=headers, tablefmt="rounded_grid"))


def format_pretty_artifact(data):
    """
    This command will print a table for the artifact returned by the show command.
    """
    # Extract the list from your dictionary
    # rows = data.get('parameter', [])
    headers = ["id", "name", "Pointer"]

    # Print a clean, formatted table
    print(tabulate(data, headers=headers, tablefmt="rounded_grid"))


def command(engine, storage_root, args):
    """CLI Show Command Handler"""
    
    # 1. Ask the Core API for the pure data
    data = get_run_details(
        engine=engine,
        run_names=args.get("run_name"),
        params=args.get("parameter"),
        meta=args.get("metadata"),
        results=args.get("result")
    )
    
    # 2. Paint the data to the terminal
    if "parameter" in data and data["parameter"]:
        format_pretty(data["parameter"], "Parameter")
        
    if "metadata" in data and data["metadata"]:
        format_pretty(data["metadata"], "Metadata")
        
    if "result" in data and data["result"]:
        format_pretty(data["result"], "Result")
        
    if "artifacts" in data and data["artifacts"]:
        format_pretty_artifact(data["artifacts"])
        
    return data
