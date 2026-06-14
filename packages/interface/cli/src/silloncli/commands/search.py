import ast

from rich.console import Console
from rich.table import Table

from silloncore.engine import query_runs


def add_parser(command_subparser):
    # -- Parser for the search command -- #
    search_parser = command_subparser.add_parser(
        "search", help="Find runs by parameter value, or by result/artifact presence."
    )
    search_parser.add_argument(
        "-p",
        "--parameter",
        nargs="+",
        type=str,
        default=None,
        metavar="KEY=VALUE",
        help="Parameter equality filter, e.g. -p optimizer=adam lr=0.01",
    )
    search_parser.add_argument(
        "-r",
        "--result",
        nargs="+",
        type=str,
        default=None,
        help="Keep runs that have these result name(s).",
    )
    search_parser.add_argument(
        "-a",
        "--artifact",
        nargs="+",
        type=str,
        default=None,
        help="Keep runs that have these artifact name(s).",
    )
    search_parser.add_argument(
        "--limit", type=int, default=None, help="Limit the number of results shown."
    )


def _parse_value(raw: str):
    """Best-effort literal parse so `0.01`/`true` aren't compared as strings."""
    try:
        return ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return raw


def command(engine, storage_root, args):
    """CLI Search Command Handler"""
    console = Console()

    parameters = None
    if args.get("parameter"):
        parameters = {}
        for item in args["parameter"]:
            if "=" not in item:
                console.print(f"[red]Ignoring '{item}': expected KEY=VALUE.[/red]")
                continue
            key, raw = item.split("=", 1)
            parameters[key] = _parse_value(raw)

    names = query_runs(
        engine,
        parameters=parameters,
        results=args.get("result"),
        artifacts=args.get("artifact"),
    )

    limit = args.get("limit")
    if limit is not None:
        names = names[:limit]

    if not names:
        console.print("[yellow]No runs matched the query.[/yellow]")
        return names

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Run name", style="bold white")
    for i, name in enumerate(names, 1):
        table.add_row(str(i), name)
    console.print(table)
    console.print(f"[dim]{len(names)} run(s) matched.[/dim]")
    return names
