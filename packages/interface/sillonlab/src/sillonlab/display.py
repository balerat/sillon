"""Rich rendering helpers for sillonlab.

These functions only paint data already fetched through silloncore.engine:
no database or storage access happens here. They work both in a terminal
and in a jupyter notebook (rich handles the frontend).
"""

from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_console = Console()

_STATUS_STYLE = {
    "SUCCESS": "bold green",
    "FAILED": "bold red",
    "FAILURE": "bold red",
    "KILLED": "bold red",
    "RUNNING": "bold yellow",
}


def _status_text(status) -> Text:
    status = str(status or "N/A")
    return Text(status, style=_STATUS_STYLE.get(status, "dim"))


def _human_size(nbytes: int) -> str:
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{int(nbytes)} B"


def print_context(data: dict, project_name: str = "") -> None:
    """Pretty-prints an engine `get_project_context` payload.

    Args:
        data (dict): The payload returned by the engine (`mode` + `runs`).
        project_name (str): The project name shown in the panel title.
    """
    if data["mode"] == "overview":
        _print_overview(data["runs"], project_name)
    else:
        _print_specific(data["runs"])


def _print_overview(runs: list, project_name: str) -> None:
    table = Table(
        show_header=True, header_style="bold magenta", box=None, padding=(0, 2)
    )
    table.add_column("Run Name", style="bold white")
    table.add_column("Timestamp", style="dim")
    table.add_column("Params", justify="center")
    table.add_column("Assets", justify="center", style="green")
    table.add_column("Status", justify="center")

    for run in runs:
        table.add_row(
            str(run["name"]),
            str(run["timestamp"]),
            str(run["param_count"]),
            str(run["asset_count"]),
            _status_text(run["status"]),
        )

    title = f"[bold]{project_name}[/bold]" if project_name else "[bold]Project[/bold]"
    _console.print(
        Panel(
            Group(
                Text(f"{len(runs)} runs logged in the project\n", style="italic yellow"),
                table,
            ),
            border_style="bright_red",
            padding=(1, 2),
            title=title,
            subtitle="[dim]sillonlab[/dim]",
        )
    )


def _print_specific(runs: list) -> None:
    run_cards = []
    for run in runs:
        content = Group(
            Text.assemble(("Run Name: ", "bold cyan"), (str(run["name"]), "white")),
            Text.assemble(("Time:     ", "bold dim"), (str(run["timestamp"]), "dim")),
            Text(
                f"Params:   {run['param_count']} | Assets: {run['asset_count']}",
                style="green",
            ),
            Text(f"Runtime:  {run.get('runtime', 'N/A')}", style="italic"),
            Text(f"Language: {run.get('language', 'N/A')}", style="italic"),
            Text.assemble(("Status:   ", "italic"), _status_text(run.get("status"))),
        )
        run_cards.append(
            Panel(
                content,
                title=f"[bold white]{run['name']}[/bold white]",
                border_style="bright_red",
                padding=(1, 2),
                expand=False,
            )
        )
    _console.print(Columns(run_cards, equal=True, expand=False))


def print_run(run) -> None:
    """Pretty-prints a single `Run` as a detail card.

    Args:
        run (Run): The run handle to display (data is loaded on access).
    """
    parameters = run.parameters

    table = Table(show_header=True, header_style="bold magenta", box=None)
    table.add_column("Parameter", style="cyan")
    table.add_column("Value", style="white")
    for key, value in parameters.items():
        text = str(value)
        if len(text) > 60:
            text = text[:57] + "..."
        table.add_row(key, text)

    sizes = run.sizes()

    def _result_line(name: str) -> Text:
        size = sizes.get(name)
        suffix = f" ({_human_size(size['bytes'])})" if size else ""
        return Text(f"  {name}{suffix}", style="white")

    lines = [
        Text.assemble(("Timestamp: ", "bold dim"), (str(run.timestamp), "dim")),
        Text.assemble(("Status:    ", "bold dim"), _status_text(run.status)),
        Text.assemble(("Runtime:   ", "bold dim"), (str(run.runtime or "N/A"), "dim")),
        Text(""),
        table,
        Text(""),
        Text("Results:", style="bold green"),
    ]
    lines += [_result_line(name) for name in run.results] or [Text("  none", style="dim")]

    figures = run.figures
    if figures:
        lines.append(Text("Figures:", style="bold blue"))
        for name, meta in figures.items():
            used = meta.get("used") or []
            provenance = f"  ← built from: {', '.join(used)}" if used else ""
            caption = f"  \"{meta['caption']}\"" if meta.get("caption") else ""
            lines.append(Text(f"  {name}{provenance}{caption}", style="white"))

    analyses = run.analyses
    if analyses:
        lines.append(Text("Analyses:", style="bold cyan"))
        for name, meta in analyses.items():
            comment = f"  ({meta['comment']})" if meta.get("comment") else ""
            lines.append(_result_line(name).append(comment, style="dim"))

    if run.tags:
        lines.append(Text.assemble(("Tags:    ", "bold yellow"), (", ".join(run.tags))))
    for note in run.notes:
        lines.append(Text(f"• {note}", style="italic"))

    _console.print(
        Panel(
            Group(*lines),
            title=f"[bold white]{run.name}[/bold white]",
            border_style="bright_red",
            padding=(1, 2),
            expand=False,
        )
    )


def print_run_table(runs) -> None:
    """Pretty-prints a `RunCollection` as a summary table.

    Args:
        runs (RunCollection | list[Run]): The runs to display.
    """
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Run Name", style="bold white")
    table.add_column("Timestamp", style="dim")
    table.add_column("Params", justify="center")
    table.add_column("Results", justify="center", style="green")
    table.add_column("Tags", style="yellow")
    table.add_column("Status", justify="center")

    for run in runs:
        table.add_row(
            run.name,
            str(run.timestamp),
            str(len(run.parameters)),
            str(len(run.results)),
            ", ".join(run.tags),
            _status_text(run.status),
        )

    _console.print(table)
