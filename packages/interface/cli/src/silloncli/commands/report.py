from rich.console import Console

from silloncore.engine import get_run_snapshot, export_run_report


def add_parser(command_subparser):
    # -- Parser for the report command -- #
    report_parser = command_subparser.add_parser(
        "report", help="Export a self-contained context bundle (zip) describing a run."
    )
    report_parser.add_argument(
        "run_name", type=str, help="The name or uuid of the run."
    )
    report_parser.add_argument(
        "--dest",
        type=str,
        default=None,
        help="Output zip path (defaults to <run>_report.zip).",
    )
    report_parser.add_argument(
        "--with-data",
        action="store_true",
        help="Also embed the run's results/analyses as HDF5 in the bundle.",
    )


def command(engine, storage_root, args):
    """CLI Report Command Handler"""
    console = Console()

    snapshot = get_run_snapshot(engine, args["run_name"])
    if snapshot is None:
        console.print(f"[bold red]✖ Error:[/bold red] Run '{args['run_name']}' not found.")
        return None

    path = export_run_report(
        engine,
        storage_root,
        snapshot,
        dest=args.get("dest"),
        with_data=args.get("with_data", False),
    )
    console.print(f"[bold green]✔[/bold green] Wrote report bundle to [cyan]{path}[/cyan]")
    return path
