import ast

from rich.console import Console
from rich.table import Table

from silloncore.engine import query_runs


def add_parser(command_subparser):
    # -- Parser for the search command -- #
    search_parser = command_subparser.add_parser(
        "search",
        help="Find runs by parameter/metadata value, tag, date, or result/artifact presence.",
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
        "-m",
        "--meta",
        nargs="+",
        type=str,
        default=None,
        metavar="KEY=VALUE",
        help="Metadata equality filter, e.g. -m sillon.language=python",
    )
    search_parser.add_argument(
        "-t",
        "--tag",
        nargs="+",
        type=str,
        default=None,
        help="Keep runs that have these tag(s).",
    )
    search_parser.add_argument(
        "--status", type=str, default=None, help="Keep runs with this status."
    )
    search_parser.add_argument(
        "--before", type=str, default=None, metavar="DATE",
        help="Keep runs created before DATE (YYYY-MM-DD).",
    )
    search_parser.add_argument(
        "--after", type=str, default=None, metavar="DATE",
        help="Keep runs created after DATE (YYYY-MM-DD).",
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
        "-A",
        "--analysis",
        nargs="+",
        type=str,
        default=None,
        help="Keep runs that have these analysis name(s).",
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

    def _parse_kv(items):
        """Parses a list of KEY=VALUE strings into an equality-conditions dict."""
        if not items:
            return None
        out = {}
        for item in items:
            if "=" not in item:
                console.print(f"[red]Ignoring '{item}': expected KEY=VALUE.[/red]")
                continue
            key, raw = item.split("=", 1)
            out[key] = _parse_value(raw)
        return out or None

    fields = {"status": args["status"]} if args.get("status") else None

    # The shell expresses equality (-p/-m KEY=VALUE, --status), presence
    # filters (-r/-a/-A/-t), and date bounds; value predicates are a
    # programmatic (sillonlab) feature.
    names = query_runs(
        engine,
        storage_root,
        parameters=_parse_kv(args.get("parameter")),
        metadata=_parse_kv(args.get("meta")),
        fields=fields,
        has_result=args.get("result"),
        has_artifact=args.get("artifact"),
        has_analysis=args.get("analysis"),
        has_tag=args.get("tag"),
        before=args.get("before"),
        after=args.get("after"),
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
