from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table
from silloncore.engine import compare


def add_parser(command_subparser):
    # -- Parser for the add command -- #
    add_parser = command_subparser.add_parser("compare")
    add_parser.add_argument(
        "run_name",
        nargs="+",
        type=str,
        help="The UUIDs, IDs, or names of the runs",
    )


def command(engine, storage_root, args):
    """CLI Compare command (just working now for 2 sim with their dates)"""
    console = Console()

    if len(args.get("run_name")) != 2:
        raise ValueError("Please give two run name")
    else:
        run1, run2 = args.get("run_name")

    result = compare(engine, run1, run2)

    if result["status"] != "success":
        raise ValueError("[CLI]: compare is no_success")
    syntax_source_diff = Syntax(
        result["diff_source"], "diff", theme="monokai", line_numbers=True
    )
    console.rule(f"[bold cyan]Comparing: {run1} vs {run2}[/bold cyan]")

    # 2. Pretty Parameters Table
    diff_param = result.get("diff_param")
    if diff_param:
        added = diff_param.get("diff_key_added", set())
        removed = diff_param.get("diff_key_removed", set())

        # Filter out keys that returned None (meaning no actual difference)
        changed = {
            k: v for k, v in diff_param.get("diff_data", {}).items() if v is not None
        }

        # Only draw the table if there is actual data
        if added or removed or changed:
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("Parameter", style="cyan")
            table.add_column("State", style="bold")
            table.add_column("Details", style="white")

            for key in added:
                table.add_row(key, "[green]+ Added[/green]", "")
            for key in removed:
                table.add_row(key, "[red]- Removed[/red]", "")
            for key, val in changed.items():
                # val is expected to be a tuple (old, new, percent) from your previous logic
                table.add_row(
                    key, "[yellow]~ Changed[/yellow]", f"{val[0]} -> {val[1]}"
                )

            console.print(table)
        else:
            console.print("[dim]Parameters are identical.[/dim]")
    diff_status = result.get("diff_status")
    diff_runtime = result.get("diff_runtime")

    if diff_status or diff_runtime:
        console.print("\n[bold yellow]Context Differences:[/bold yellow]")
        if diff_status:
            console.print(f"  • Status:  {diff_status[0]} -> {diff_status[1]}")
        if diff_runtime:
            console.print(f"  • Runtime: {diff_runtime[0]} -> {diff_runtime[1]}")

    diff_source = result.get("diff_source", "")
    if diff_source and diff_source.strip():
        console.rule("[bold red]Source Code Diff[/bold red]")
        syntax_source_diff = Syntax(
            diff_source, "diff", theme="monokai", line_numbers=True
        )
        console.print(syntax_source_diff)
    else:
        console.print("\n[dim]Source code is identical.[/dim]")
