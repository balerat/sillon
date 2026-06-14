from rich.console import Console

from silloncore.engine import get_run_snapshot, fetch_run_result


def add_parser(command_subparser):
    # -- Parser for the grab command -- #
    grab_parser = command_subparser.add_parser(
        "grab", help="Fetch a result, artifact, or figure of a run as a file on disk."
    )
    grab_parser.add_argument(
        "run_name", type=str, help="The name or uuid of the run."
    )
    grab_parser.add_argument(
        "-r",
        "--result",
        required=True,
        type=str,
        help="The result, artifact, or figure name to fetch.",
    )
    grab_parser.add_argument(
        "--dest",
        type=str,
        default=None,
        help="Destination directory (defaults to the current directory).",
    )


def command(engine, storage_root, args):
    """CLI Grab Command Handler"""
    console = Console()

    snapshot = get_run_snapshot(engine, args["run_name"])
    if snapshot is None:
        console.print(f"[bold red]✖ Error:[/bold red] Run '{args['run_name']}' not found.")
        return None

    try:
        path = fetch_run_result(storage_root, snapshot, args["result"], args.get("dest"))
    except LookupError as e:
        console.print(f"[bold red]✖ Error:[/bold red] {e}")
        return None

    console.print(f"[bold green]✔[/bold green] Fetched to [cyan]{path}[/cyan]")
    return path
