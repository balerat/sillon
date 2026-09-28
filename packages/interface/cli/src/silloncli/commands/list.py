from silloncore.engine import get_project_context
from silloncore.display import print_context
from silloncore.project_paths import resolve_project_name


def add_parser(command_subparser):
    list_parser = command_subparser.add_parser(
        "list", help="List the runs of this project."
    )
    list_parser.add_argument(
        "run_name",
        nargs="*",
        type=str,
        help="Limit the table to these runs (omit for all of them).",
    )


def command(engine, storage_root, args):
    """CLI List Command Handler — the project's runs as a table.

    One run in detail is `sillon show`; this is the many-runs view.
    """
    from pathlib import Path

    data = get_project_context(engine, args.get("run_name", []))
    # The overview shape is the table; the per-run shape is a detail card,
    # which is `show`'s job, so always render the table here.
    data["mode"] = "overview"
    print_context(data, project_name=resolve_project_name(Path.cwd()))
    return data
