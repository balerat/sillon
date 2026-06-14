from rich.console import Console
from silloncore.engine import add_metadata_to_runs

def add_parser(command_subparser):
    # -- Parser for the add command -- #
    add_parser = command_subparser.add_parser("add")
    add_parser.add_argument(
        "run_name",
        nargs="*",
        type=str,
        help="The UUIDs, IDs, or names of the runs",
    )
    add_parser.add_argument(
        "-n",
        "--note",
        nargs="+",
        type=str,
    )
    add_parser.add_argument(
        "-t",
        "--tag",
        nargs="+",
        type=str,
    )

def command(engine, storage_root, args):
    """CLI Add Command Handler"""
    console = Console()
    
    # 1. Ask the Core API to do the heavy lifting
    result = add_metadata_to_runs(
        engine=engine,
        run_names=args.get("run_name", []),
        notes=args.get("note"),
        tags=args.get("tag")
    )
    
    # 2. Paint the terminal based on the response
    if result["status"] == "success":
        console.print(f"[bold green]✔ Success:[/bold green] Updated {result['updated_count']} run(s).")
        
        # Give specific feedback on what was actually added
        if result["added_tags"] > 0:
            console.print(f"  [dim]• Added {result['added_tags']} tag(s)[/dim]")
        if result["added_notes"] > 0:
            console.print(f"  [dim]• Added {result['added_notes']} note(s)[/dim]")
            
    elif result["status"] == "warning":
        console.print(f"[bold yellow]⚠ Notice:[/bold yellow] {result['message']}")
        
    elif result["status"] == "error":
        console.print(f"[bold red]✖ Error:[/bold red] {result['message']}")
        
    return result
