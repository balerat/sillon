import ast

from silloncore.bundle import BundleError
from silloncore.display import console, print_export_result


def add_parser(command_subparser):
    export_parser = command_subparser.add_parser(
        "export",
        help="Write runs to a portable bundle another machine can import.",
    )
    export_parser.add_argument(
        "run_name",
        nargs="*",
        type=str,
        default=None,
        help="Runs to export. Omit for every run matching the filters, or the whole project.",
    )
    export_parser.add_argument(
        "--dest",
        type=str,
        default=None,
        help="A file to write, or a directory to write a self-describing name into.",
    )
    export_parser.add_argument(
        "--no-data",
        action="store_true",
        help="Index only: no arrays, artifacts or figures. The runs import as stubs.",
    )
    # The same filters as `sillon query`, so there is one filter vocabulary.
    export_parser.add_argument(
        "-p", "--parameter", nargs="+", default=None, metavar="KEY=VALUE",
        help="Only runs whose parameter equals this value.",
    )
    export_parser.add_argument(
        "-m", "--metadata", nargs="+", default=None, metavar="KEY=VALUE",
        help="Only runs whose metadata equals this value.",
    )
    export_parser.add_argument(
        "-t", "--tag", nargs="+", default=None, help="Only runs with these tags."
    )
    export_parser.add_argument(
        "--status", type=str, default=None, help="Only runs with this status."
    )
    export_parser.add_argument(
        "--before", type=str, default=None, help="Only runs before this date."
    )
    export_parser.add_argument(
        "--after", type=str, default=None, help="Only runs after this date."
    )


def _pairs(raw):
    """`KEY=VALUE` arguments into a dict, values as Python literals."""
    if not raw:
        return None
    out = {}
    for item in raw:
        if "=" not in item:
            continue
        key, _, value = item.partition("=")
        try:
            out[key] = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            out[key] = value
    return out or None


def command(engine, storage_root, args):
    """CLI Export Command Handler"""
    from pathlib import Path

    from silloncore.engine import export_bundle

    filters = {}
    if _pairs(args.get("parameter")):
        filters["parameters"] = _pairs(args["parameter"])
    if _pairs(args.get("metadata")):
        filters["metadata"] = _pairs(args["metadata"])
    if args.get("tag"):
        filters["has_tag"] = args["tag"]
    if args.get("status"):
        filters["fields"] = {"status": args["status"]}
    if args.get("before"):
        filters["before"] = args["before"]
    if args.get("after"):
        filters["after"] = args["after"]

    try:
        result = export_bundle(
            engine,
            storage_root,
            Path.cwd(),
            run_names=args.get("run_name") or None,
            dest=args.get("dest"),
            with_data=not args.get("no_data"),
            **filters,
        )
    except BundleError as exc:
        console.print(f"[bold red]✖ Error:[/bold red] {exc}")
        return None

    print_export_result(result)
    return result
