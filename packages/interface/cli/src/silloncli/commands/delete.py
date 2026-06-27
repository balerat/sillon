from rich.console import Console

from silloncore.engine import delete_run


def add_parser(command_subparser):
    # -- Parser for the delete command -- #
    delete_parser = command_subparser.add_parser(
        "delete", help="Permanently delete a run (its stored data and database row)."
    )
    delete_parser.add_argument(
        "run_name",
        nargs="+",
        type=str,
        help="The name(s) or uuid(s) of the run(s) to delete.",
    )
    delete_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )


def command(engine, storage_root, args):
    """CLI Delete Command Handler"""
    console = Console()
    run_names = args.get("run_name", [])

    if not args.get("yes"):
        console.print(
            f"[bold yellow]This permanently deletes:[/bold yellow] {', '.join(run_names)}"
        )
        answer = input("Continue? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            console.print("[dim]Aborted.[/dim]")
            return None

    results = []
    for name in run_names:
        result = delete_run(engine, storage_root, name)
        results.append(result)
        if result["status"] == "success":
            freed_mb = result["freed_bytes"] / (1024 * 1024)
            console.print(
                f"[bold green]✔[/bold green] Deleted [cyan]{result['deleted']}[/cyan] "
                f"(freed {freed_mb:.2f} MB)"
            )
        else:
            console.print(f"[bold red]✖ Error:[/bold red] {result['message']}")

    return results
