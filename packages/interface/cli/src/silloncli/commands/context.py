from silloncore.engine import get_project_context
from silloncore.display import print_context


def add_parser(command_subparser):
    context_parser = command_subparser.add_parser(
        "context", help="Project overview, or a detail card per run."
    )
    context_parser.add_argument(
        "run_name",
        nargs="*",
        type=str,
        help="The names or uuids of the runs (omit for the whole-project overview).",
    )


def command(engine, storage_root, args):
    """CLI Context Command Handler — themed overview / per-run cards."""
    data = get_project_context(engine, args.get("run_name", []))
    print_context(data)
    return data
