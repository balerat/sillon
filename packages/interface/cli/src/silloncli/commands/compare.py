from rich.syntax import Syntax

from silloncore.engine import compare
from silloncore.display import console, themed_table, format_value, c


def add_parser(command_subparser):
    compare_parser = command_subparser.add_parser(
        "compare", help="Diff two runs (parameters, context, and source)."
    )
    compare_parser.add_argument(
        "run_name",
        nargs="+",
        type=str,
        help="The two run names or uuids to compare.",
    )


def command(engine, storage_root, args):
    """CLI Compare command — themed parameter / context / source diff."""
    if len(args.get("run_name")) != 2:
        raise ValueError("Please give two run names")
    run1, run2 = args.get("run_name")

    result = compare(engine, run1, run2)
    if result["status"] != "success":
        raise ValueError("[CLI]: compare did not succeed")

    console.rule(f"[bold {c('foam')}]Comparing: {run1} vs {run2}[/]")

    diff_param = result.get("diff_param")
    if diff_param:
        added = diff_param.get("diff_key_added", set())
        removed = diff_param.get("diff_key_removed", set())
        changed = {
            k: v for k, v in diff_param.get("diff_data", {}).items() if v is not None
        }

        if added or removed or changed:
            table = themed_table()
            table.add_column("Parameter", style=c("foam"))
            table.add_column("State", style="bold")
            table.add_column("Details", style=c("spray"))

            for key in added:
                table.add_row(key, "[#6FCF8E]+ added[/]", "")
            for key in removed:
                table.add_row(key, "[#E06C75]- removed[/]", "")
            for key, val in changed.items():
                table.add_row(
                    key,
                    f"[{c('ember')}]~ changed[/]",
                    f"{format_value(val[0])} → {format_value(val[1])}",
                )
            console.print(table)
        else:
            console.print(f"[{c('slate')}]Parameters are identical.[/]")

    diff_status = result.get("diff_status")
    diff_runtime = result.get("diff_runtime")
    if diff_status or diff_runtime:
        console.print(f"\n[bold {c('ember')}]Context differences:[/]")
        if diff_status:
            console.print(f"  • Status:  {diff_status[0]} → {diff_status[1]}")
        if diff_runtime:
            console.print(f"  • Runtime: {diff_runtime[0]} → {diff_runtime[1]}")

    diff_source = result.get("diff_source", "")
    if diff_source and diff_source.strip():
        console.rule(f"[bold {c('wake')}]Source code diff[/]")
        console.print(Syntax(diff_source, "diff", theme="monokai", line_numbers=True))
    else:
        console.print(f"\n[{c('slate')}]Source code is identical.[/]")
