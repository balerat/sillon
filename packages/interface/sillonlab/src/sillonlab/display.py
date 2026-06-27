"""Rich rendering helpers for sillonlab.

These functions only paint data already fetched through silloncore.engine:
no database or storage access happens here. They work both in a terminal
and in a jupyter notebook (rich handles the frontend).

The palette mirrors the sillon website: wake-blue carries structure
(headers, borders), foam-cyan is the highlight/active signal, ember is the
single warm accent, and the abyss/hull tones fill backgrounds.
"""

from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

_console = Console()

# --- palette (shared with the website) -------------------------------------
_COLORS = {
    "abyss": "#0A1828",
    "hull": "#0E2438",
    "hull_2": "#102b44",
    "wake": "#1B6CA8",
    "foam": "#3DD4D4",
    "ember": "#F2A65A",
    "ember_soft": "#F4B97E",
    "spray": "#C7D7E3",
    "slate": "#5A7A94",
}


def c(name: str) -> str:
    """Return a palette hex by name (keeps style strings readable)."""
    return _COLORS[name]


# --- reusable style strings -------------------------------------------------
# Foreground-on-background pairs do the "filled box/table" look.
S_HEADER = f"bold {c('abyss')} on {c('foam')}"          # table headers: foam fill
S_BORDER = c("wake")                                     # box borders: wake blue
S_TITLE = f"bold {c('spray')}"
S_LABEL = f"bold {c('slate')}"                           # left-hand field labels
S_VALUE = c("spray")                                     # field values
S_ACCENT = c("foam")                                     # highlighted values
S_EMBER = c("ember")                                     # warm accent (tags etc.)
S_DIM = c("slate")
S_PANEL_BG = f"on {c('hull')}"                           # interior fill for panels
S_ZEBRA = [f"on {c('hull')}", f"on {c('hull_2')}"]       # alternating row fills

_STATUS_STYLE = {
    "SUCCESS": f"bold #6FCF8E on {c('hull')}",
    "FAILED": f"bold #E06C75 on {c('hull')}",
    "FAILURE": f"bold #E06C75 on {c('hull')}",
    "KILLED": f"bold #E06C75 on {c('hull')}",
    "RUNNING": f"bold {c('ember')} on {c('hull')}",
}


def _status_text(status) -> Text:
    status = str(status or "N/A")
    return Text(f" {status} ", style=_STATUS_STYLE.get(status, f"{c('slate')} on {c('hull')}"))


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
        show_header=True,
        header_style=S_HEADER,
        box=box.SIMPLE_HEAVY,
        padding=(0, 2),
        border_style=S_BORDER,
        row_styles=S_ZEBRA,
        expand=True,
    )
    table.add_column("Run Name", style=f"bold {c('spray')}")
    table.add_column("Timestamp", style=S_DIM)
    table.add_column("Params", justify="center", style=c("wake"))
    table.add_column("Assets", justify="center", style=c("foam"))
    table.add_column("Status", justify="center")

    for run in runs:
        table.add_row(
            str(run["name"]),
            str(run["timestamp"]),
            str(run["param_count"]),
            str(run["asset_count"]),
            _status_text(run["status"]),
        )

    title = f"[bold {c('spray')}]{project_name or 'Project'}[/]"
    subtitle = Text(
        f"{len(runs)} runs logged in the project", style=f"italic {c('ember')}"
    )
    _console.print(
        Panel(
            Group(subtitle, Text(""), table),
            title=title,
            title_align="left",
            border_style=S_BORDER,
            style=S_PANEL_BG,
            padding=(1, 2),
        )
    )


def _print_specific(runs: list) -> None:
    run_cards = []
    for run in runs:
        content = Group(
            Text.assemble(("Run Name  ", S_LABEL), (str(run["name"]), S_ACCENT)),
            Text.assemble(("Time      ", S_LABEL), (str(run["timestamp"]), S_DIM)),
            Text.assemble(
                ("Params    ", S_LABEL),
                (str(run["param_count"]), S_VALUE),
                ("   Assets  ", S_LABEL),
                (str(run["asset_count"]), c("foam")),
            ),
            Text.assemble(("Runtime   ", S_LABEL), (str(run.get("runtime", "N/A")), S_VALUE)),
            Text.assemble(("Language  ", S_LABEL), (str(run.get("language", "N/A")), S_VALUE)),
            Text.assemble(("Status    ", S_LABEL), _status_text(run.get("status"))),
        )
        run_cards.append(
            Panel(
                content,
                title=f"[bold {c('spray')}]{run['name']}[/]",
                title_align="left",
                border_style=S_BORDER,
                style=S_PANEL_BG,
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

    table = Table(
        show_header=True,
        header_style=S_HEADER,
        box=box.SIMPLE,
        row_styles=S_ZEBRA,
        expand=True,
    )
    table.add_column("Parameter", style=c("foam"))
    table.add_column("Value", style=S_VALUE)
    for key, value in parameters.items():
        text = str(value)
        if len(text) > 60:
            text = text[:57] + "..."
        table.add_row(key, text)

    sizes = run.sizes()

    def _result_line(name: str) -> Text:
        size = sizes.get(name)
        suffix = f" ({_human_size(size['bytes'])})" if size else ""
        return Text.assemble((f"  {name}", S_VALUE), (suffix, S_DIM))

    lines = [
        Text.assemble(("Timestamp  ", S_LABEL), (str(run.timestamp), S_DIM)),
        Text.assemble(("Status     ", S_LABEL), _status_text(run.status)),
        Text.assemble(("Runtime    ", S_LABEL), (str(run.runtime or "N/A"), S_DIM)),
        Text(""),
        table,
        Text(""),
        Text("Results", style=f"bold {c('foam')}"),
    ]
    lines += [_result_line(name) for name in run.results] or [Text("  none", style=S_DIM)]

    figures = run.figures
    if figures:
        lines.append(Text("Figures", style=f"bold {c('wake')}"))
        for name, meta in figures.items():
            used = meta.get("used") or []
            provenance = f"  ← built from: {', '.join(used)}" if used else ""
            caption = f"  \"{meta['caption']}\"" if meta.get("caption") else ""
            lines.append(
                Text.assemble(
                    (f"  {name}", S_VALUE),
                    (provenance, S_DIM),
                    (caption, f"italic {c('slate')}"),
                )
            )

    analyses = run.analyses
    if analyses:
        lines.append(Text("Analyses", style=f"bold {c('foam')}"))
        for name, meta in analyses.items():
            comment = f"  ({meta['comment']})" if meta.get("comment") else ""
            lines.append(_result_line(name).append(comment, style=S_DIM))

    if run.tags:
        tag_text = Text("Tags       ", style=S_LABEL)
        for i, tag in enumerate(run.tags):
            if i:
                tag_text.append("  ", style=S_DIM)
            tag_text.append(f" {tag} ", style=f"{c('abyss')} on {c('ember')}")
        lines.append(tag_text)
    for note in run.notes:
        lines.append(Text(f"• {note}", style=f"italic {c('slate')}"))

    _console.print(
        Panel(
            Group(*lines),
            title=f"[bold {c('spray')}]{run.name}[/]",
            title_align="left",
            border_style=S_BORDER,
            style=S_PANEL_BG,
            padding=(1, 2),
            expand=False,
        )
    )


def print_run_table(runs) -> None:
    """Pretty-prints a `RunCollection` as a summary table.

    Args:
        runs (RunCollection | list[Run]): The runs to display.
    """
    table = Table(
        show_header=True,
        header_style=S_HEADER,
        box=box.SIMPLE_HEAVY,
        border_style=S_BORDER,
        row_styles=S_ZEBRA,
        pad_edge=False,
        expand=True,
    )
    table.add_column("Run Name", style=f"bold {c('spray')}")
    table.add_column("Timestamp", style=S_DIM)
    table.add_column("Params", justify="center", style=c("wake"))
    table.add_column("Results", justify="center", style=c("foam"))
    table.add_column("Tags", style=c("ember"))
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