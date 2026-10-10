"""`sillon import` — the module is `import_cmd` because `import` is a keyword."""

from silloncli.context import project_root
from silloncore.bundle import BundleError
from silloncore.display import (
    console,
    print_import_plan,
    print_import_result,
    print_scan_result,
)


def add_parser(command_subparser):
    import_parser = command_subparser.add_parser(
        "import",
        help="Add the runs from a bundle or another project that this one does not have.",
    )
    import_parser.add_argument(
        "source",
        type=str,
        help="A bundle written by `sillon export`, or another project directory.",
    )
    import_parser.add_argument(
        "--scan",
        action="store_true",
        help="Treat the source as a directory to search, and import every project under it.",
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
        help="Describe the source without looking at this project at all.",
    )


def command(engine, storage_root, args):
    """CLI Import Command Handler"""
    from silloncore.engine import import_from, inspect_bundle, scan_and_import

    with_data = not args.get("no_data")
    dry_run = bool(args.get("dry_run"))

    try:
        if args.get("scan"):
            if args.get("inspect"):
                console.print(
                    "[bold red]✖ Error:[/bold red] --inspect describes one source; "
                    "use --scan --dry-run to see what a tree would bring in."
                )
                return None
            result = scan_and_import(
                engine,
                storage_root,
                project_root(),
                args["source"],
                with_data=with_data,
                dry_run=dry_run,
            )
            print_scan_result(result)
            return result

        if args.get("inspect"):
            described = inspect_bundle(args["source"])
            print_import_plan({"source": described, "inspect_only": True})
            return described

        result = import_from(
            engine, storage_root, args["source"], with_data=with_data, dry_run=dry_run
        )
    except BundleError as exc:
        console.print(f"[bold red]✖ Error:[/bold red] {exc}")
        return None

    if result.get("dry_run"):
        print_import_plan(result)
    else:
        print_import_result(result)
    return result
