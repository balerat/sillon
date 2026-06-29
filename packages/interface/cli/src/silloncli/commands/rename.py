from silloncore.engine import rename_run
from silloncore.display import console


def add_parser(command_subparser):
    rename_parser = command_subparser.add_parser(
        "rename", help="Rename a run (rejected if the new name is taken)."
    )
    rename_parser.add_argument("run_name", type=str, help="The current name, uuid, or uuid prefix.")
    rename_parser.add_argument("new_name", type=str, help="The new name.")


def command(engine, storage_root, args):
    """CLI Rename Command Handler."""
    result = rename_run(engine, args["run_name"], args["new_name"])
    if result["status"] == "success":
        console.print(
            f"[bold green]✔[/bold green] Renamed "
            f"[cyan]{result['old']}[/cyan] → [cyan]{result['new']}[/cyan]"
        )
    else:
        console.print(f"[bold red]✖ Error:[/bold red] {result['message']}")
    return result
