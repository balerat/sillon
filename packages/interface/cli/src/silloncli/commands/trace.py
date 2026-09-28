from silloncore.engine import trace
from silloncore.display import console, themed_table, c


def add_parser(command_subparser):
    trace_parser = command_subparser.add_parser(
        "trace", help="Identify which run a file (or hash) belongs to."
    )
    trace_parser.add_argument(
        "file", type=str, help="A file path (it gets hashed) or a SHA-256 hash."
    )


def command(engine, storage_root, args):
    """CLI Trace Command Handler — trace a file back to its run."""
    matches = trace(engine, args["file"])

    if not matches:
        console.print(f"[yellow]No run owns[/] [b]{args['file']}[/b] [yellow](hash not found).[/]")
        return matches

    table = themed_table()
    table.add_column("Kind", style=c("wake"))
    table.add_column("Name", style=c("foam"))
    table.add_column("Run", style=f"bold {c('spray')}")
    for m in matches:
        table.add_row(m["kind"], m["name"], m["run_name"])
    console.print(table)
    return matches
