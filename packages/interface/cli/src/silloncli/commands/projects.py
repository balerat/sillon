from silloncore.projects import get_projects, prune_projects, repair_registry
from silloncore.display import print_projects


def add_parser(command_subparser):
    projects_parser = command_subparser.add_parser(
        "projects",
        help="List every sillon project registered on this machine, and where it is.",
    )
    projects_parser.add_argument(
        "--prune",
        action="store_true",
        help="Forget projects whose directory no longer exists.",
    )
    projects_parser.add_argument(
        "--repair",
        action="store_true",
        help="Collapse duplicate entries left by older sillon versions.",
    )
    projects_parser.add_argument(
        "--no-stats",
        action="store_true",
        help="Skip run counts (does not open each project's database).",
    )


def command(engine, storage_root, args):
    """CLI Projects Command Handler.

    Unlike every other command this one is project-independent — it answers
    "where are my projects?", so it is dispatched before the in-a-project check
    and receives no engine.
    """
    if args.get("repair"):
        summary = repair_registry()
        print(
            f"✔ Registry repaired: {summary['removed']} duplicate entries removed "
            f"({summary['before']} → {summary['after']})."
        )

    if args.get("prune"):
        result = prune_projects()
        print(f"✔ Removed {result['removed_count']} project(s) that no longer exist.")

    records = get_projects(with_stats=not args.get("no_stats"))
    print_projects(records)
    return records
