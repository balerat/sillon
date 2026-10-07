"""`sillon import` — the module is `import_cmd` because `import` is a keyword."""

from silloncore.bundle import BundleError
from silloncore.display import console, print_import_plan, print_import_result


def add_parser(command_subparser):
    import_parser = command_subparser.add_parser(
        "import",
        help="Add the runs from a bundle that this project does not have.",
    )
    import_parser.add_argument(
        "source", type=str, help="A bundle file written by `sillon export`."
    )
    import_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen and change nothing.",
    )
    import_parser.add_argument(
        "--no-data",
        action="store_true",
        help="Import the records only, leaving the heavy data behind.",
    )
    import_parser.add_argument(
        "--inspect",
        action="store_true",
        help="Describe the bundle without looking at this project at all.",
    )


def command(engine, storage_root, args):
    """CLI Import Command Handler"""
    from silloncore.engine import import_bundle, inspect_bundle

    try:
        if args.get("inspect"):
            described = inspect_bundle(args["source"])
            print_import_plan({"source": described, "inspect_only": True})
            return described

        result = import_bundle(
            engine,
            storage_root,
            args["source"],
            with_data=not args.get("no_data"),
            dry_run=bool(args.get("dry_run")),
        )
    except BundleError as exc:
        console.print(f"[bold red]✖ Error:[/bold red] {exc}")
        return None

    if result.get("dry_run"):
        print_import_plan(result)
    else:
        print_import_result(result)
    return result
