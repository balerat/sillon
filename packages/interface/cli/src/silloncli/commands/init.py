"""`sillon init` — make this directory a project, deliberately.

A project has always come into existence as a side effect of the first run
being logged, and still does: zero-config logging is the point of sillon and
nothing here changes it. But there are two things that side effect cannot do —
name a project before it has any runs, and put its heavy data on a different
disk — and until now there was nowhere to ask for either.
"""

from pathlib import Path

from silloncore.display import console, print_init_result
from silloncore.projects import create_project


def add_parser(command_subparser):
    init_parser = command_subparser.add_parser(
        "init", help="Make this directory a sillon project."
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="The directory to initialise (defaults to the current one).",
    )
    init_parser.add_argument(
        "--name", type=str, default=None, help="The project's name."
    )
    init_parser.add_argument(
        "--storage-root",
        type=str,
        default=None,
        help="Where the heavy data should live, if not inside .sillon/.",
    )


def command(engine, storage_root, args):
    """CLI Init Command Handler.

    Dispatched before the in-a-project check, so `engine` and `storage_root`
    are always None: this is the one command whose job is to be run where
    there is no project yet.
    """
    from silloncommon.project_config import find_project_root

    target = Path(args.get("path") or Path.cwd()).expanduser().resolve()

    # Standing inside a project already. Sillon never nests projects, so the
    # useful answer is to say which one you are in rather than to make a
    # second one that shadows it.
    enclosing = find_project_root(target)
    if enclosing is not None and enclosing != target:
        console.print(
            f"[bold red]✖ Error:[/bold red] {target} is already inside the sillon "
            f"project at [cyan]{enclosing}[/cyan]."
        )
        console.print("Sillon does not nest projects. Pick a directory outside it.")
        return None

    try:
        result = create_project(
            target,
            project_name=args.get("name"),
            storage_root=args.get("storage_root"),
        )
    except OSError as exc:
        console.print(f"[bold red]✖ Error:[/bold red] {exc}")
        return None

    print_init_result(result)
    return result
