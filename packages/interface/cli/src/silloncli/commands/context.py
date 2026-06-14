# frontends/cli/commands/context.py
import argparse
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.columns import Columns

from silloncore.engine import get_project_context  # Import the new Core logic

def add_parser(command_subparser):
    # -- Parser for the context command -- #
    context_parser = command_subparser.add_parser("context")
    context_parser.add_argument(
        "run_name",
        nargs="*",
        type=str,
        help="The UUIDs, IDs, or names of the runs",
    )

def command(engine, storage_root, args):
    """CLI Context Command Handler"""
    console = Console()
    
    # 1. Ask the Core API for the pure data
    data = get_project_context(engine, args.get("run_name", []))
    
    # 2. Paint the data based on the mode
    if data["mode"] == "overview":
        runs = data["runs"]
        num_run = len(runs)
        
        ascii_logo = Text(
            r"""
      ____ ___ __  __ ____  _  __   __          ____ _     ___ 
     / ___|_ _|  \/  |  _ \| | \ \ / /         / ___| |   |_ _|
     \___ \| || |\/| | |_) | |  \ V /  _____  | |   | |    | | 
      ___) | || |  | |  __/| |___| |  |_____| | |___| |___ | | 
     |____/___|_|  |_|_|   |_____|_|           \____|_____|___|
            """,
            style="bold magenta",
        )
        
        table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 2))
        table.add_column("Run Name", style="bold white")
        table.add_column("Timestamp", style="dim")
        table.add_column("Params", justify="center")
        table.add_column("Assets", justify="center", style="green")
        table.add_column("Status", justify="center", style="green")
        
        for run in runs:
            # We now use clean dictionary keys! No more magic numbers!
            table.add_row(
                str(run["name"]), 
                str(run["timestamp"]), 
                str(run["param_count"]), 
                str(run["asset_count"]), 
                str(run["status"])
            )

        main_content = Align.center(
            Group(
                Align.center(ascii_logo),
                Align.center(Text(f"\n🚀 {num_run} Runs Found in Project\n", style="italic yellow")),
                table,
            )
        )

        console.print("\n")
        console.print(
            Panel(
                main_content,
                border_style="bright_red",
                padding=(1, 4),
                title="[bold]Project Context[/bold]",
                subtitle="[dim]v0.2.0[/dim]",
            )
        )
        
    elif data["mode"] == "specific":
        runs = data["runs"]
        console.print(f"Found {len(runs)} matches.\n")
        
        run_cards = []
        for run in runs:
            content = Group(
                Text.assemble(("Run Name: ", "bold cyan"), (f"{run['name']}", "white")),
                Text.assemble(("Time:     ", "bold dim"), (f"{run['timestamp']}", "dim")),
                Text(f"Params:   {run['param_count']} | Assets: {run['asset_count']}", style="green"),
                Text.from_markup("[bold underline]Context[/bold underline]"),
                Text(f"• Runtime:  {run['runtime']}", style="italic"),
                Text(f"• Language: {run['language']}", style="italic"),
                Text(f"• Status: {run['status']}", style="italic"),
            )

            run_cards.append(
                Panel(
                    content,
                    title=f"[bold white]{run['id']}[/bold white]",
                    border_style="bright_red",
                    padding=(1, 2),
                    expand=False, 
                )
            )

        console.print(Columns(run_cards, equal=True, expand=True))
        console.print("\n[dim]End of search results.[/dim]")
