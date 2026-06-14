from datetime import datetime, timedelta

from rich.console import Console

from silloncore.engine import prune_runs


def add_parser(command_subparser):
    # -- Parser for the prune command -- #
    prune_parser = command_subparser.add_parser(
        "prune", help="Free disk space by deleting the stored data of runs."
    )
    prune_parser.add_argument(
        "--run-id",
        nargs="+",
        type=str,
        default=None,
        help="Run name(s) or uuid(s) to prune.",
    )
    prune_parser.add_argument(
        "--older-than",
        type=str,
        default=None,
        metavar="AGE",
        help="Prune runs older than AGE: a number of days like '30d' or a date 'YYYY-MM-DD'.",
    )
    prune_parser.add_argument(
        "--delete-metadata",
        action="store_true",
        help="Also delete the database rows (default keeps metadata, drops data only).",
    )


def _parse_age(raw: str):
    """Parses '30d' (days ago) or 'YYYY-MM-DD' into a cutoff datetime."""
    if raw.endswith("d") and raw[:-1].isdigit():
        return datetime.now() - timedelta(days=int(raw[:-1]))
    return datetime.strptime(raw, "%Y-%m-%d")


def command(engine, storage_root, args):
    """CLI Prune Command Handler"""
    console = Console()

    before = None
    if args.get("older_than"):
        try:
            before = _parse_age(args["older_than"])
        except ValueError:
            console.print(
                "[bold red]✖ Error:[/bold red] --older-than must be like '30d' or 'YYYY-MM-DD'."
            )
            return None

    result = prune_runs(
        engine,
        storage_root,
        run_names=args.get("run_id"),
        before=before,
        keep_metadata=not args.get("delete_metadata", False),
    )

    if result["status"] == "error":
        console.print(f"[bold red]✖ Error:[/bold red] {result['message']}")
        return result

    freed_mb = result["freed_bytes"] / (1024 * 1024)
    console.print(
        f"[bold green]✔[/bold green] Pruned {len(result['pruned'])} run(s), "
        f"freed {freed_mb:.2f} MB."
    )
    if result["pruned"]:
        console.print(f"  [dim]{', '.join(result['pruned'])}[/dim]")
    console.print(
        f"  [dim]metadata {'kept' if result['kept_metadata'] else 'deleted'}[/dim]"
    )
    return result
