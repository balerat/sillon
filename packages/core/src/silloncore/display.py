"""Shared rich rendering theme for the sillon interfaces (CLI and sillonlab).

This module only paints data already fetched through the engine — no database
or storage access happens here. It is the single home of the sillon palette
and the reusable table/panel/run-card builders, so the CLI and the analysis
library look identical. It works both in a terminal and in a Jupyter notebook
(rich handles the frontend).

The palette mirrors the sillon website: wake-blue carries structure (headers,
borders), foam-cyan is the highlight/active signal, ember is the single warm
accent, and the abyss/hull tones fill backgrounds.

`silloncore.__init__` does not import this module, so the core logic stays
free of any rich dependency.
"""

from datetime import datetime

from rich.box import SIMPLE, SIMPLE_HEAVY
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

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
S_HEADER = f"bold {c('abyss')} on {c('foam')}"   # table headers: foam fill
S_BORDER = c("wake")                              # box borders: wake blue
S_TITLE = f"bold {c('spray')}"
S_LABEL = f"bold {c('slate')}"                    # left-hand field labels
S_VALUE = c("spray")                              # field values
S_ACCENT = c("foam")                             # highlighted values
S_EMBER = c("ember")                             # warm accent (tags etc.)
S_DIM = c("slate")
S_PANEL_BG = f"on {c('hull')}"                    # interior fill for panels
S_ZEBRA = [f"on {c('hull')}", f"on {c('hull_2')}"]  # alternating row fills

_STATUS_STYLE = {
    "SUCCESS": f"bold #6FCF8E on {c('hull')}",
    "FAILED": f"bold #E06C75 on {c('hull')}",
    "FAILURE": f"bold #E06C75 on {c('hull')}",
    "KILLED": f"bold #E06C75 on {c('hull')}",
    "RUNNING": f"bold {c('ember')} on {c('hull')}",
}


# --- small formatters -------------------------------------------------------
def status_text(status) -> Text:
    """A status rendered as a colored pill."""
    status = str(status or "N/A")
    style = _STATUS_STYLE.get(status, f"{c('slate')} on {c('hull')}")
    return Text(f" {status} ", style=style)


def human_size(nbytes: int) -> str:
    """Human-readable byte size (e.g. 1.5 KB)."""
    size = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{int(nbytes)} B"


def short_id(uuid: str, length: int = 8) -> str:
    """First `length` characters of a uuid, for compact run identification."""
    return str(uuid)[:length] if uuid else ""


def format_value(value, max_len: int = 60) -> str:
    """Render a parameter/result value compactly for display.

    Heavy array params/results stored as a `__sillon_array_ref__` marker (and
    raw ndarrays / very long lists) render as `array <dtype> (<shape>)` rather
    than dumping the marker dict or the whole array. Everything else is the
    plain string, truncated to `max_len`.
    """
    def _trunc(text):
        return text if len(text) <= max_len else text[: max_len - 3] + "..."

    # Glob-stored array marker.
    if isinstance(value, dict) and value.get("__sillon_array_ref__"):
        return _array_repr(value.get("dtype"), value.get("shape"))

    # A numpy scalar or array (duck-typed to avoid importing numpy here).
    if type(value).__module__ == "numpy" and hasattr(value, "shape"):
        size = getattr(value, "size", None)
        if size is not None and size <= 1:          # scalar / 0-d / single element
            try:
                return _trunc(str(value.item()))
            except Exception:
                return _trunc(str(value))
        if size is not None and size <= 12:         # tiny array → show the values
            return _trunc(str(value))
        return _array_repr(getattr(value, "dtype", None), list(getattr(value, "shape", ())))

    # A long sequence.
    if isinstance(value, (list, tuple)) and len(value) > 12:
        return f"{type(value).__name__} ({len(value)} items)"

    return _trunc(str(value))


def _array_repr(dtype, shape) -> str:
    shape = tuple(shape or ())
    shape_str = "(" + ", ".join(str(d) for d in shape) + ("," if len(shape) == 1 else "") + ")"
    return f"array {dtype or '?'} {shape_str}"


def relative_time(date_str: str) -> str:
    """A compact 'time ago' for the stored `%Y-%m-%d-%H:%M:%S` timestamp.

    Falls back to the raw string if it cannot be parsed.
    """
    try:
        then = datetime.strptime(str(date_str), "%Y-%m-%d-%H:%M:%S")
    except (ValueError, TypeError):
        return str(date_str)

    seconds = (datetime.now() - then).total_seconds()
    if seconds < 0:
        return "just now"
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{int(seconds // size)}{unit} ago"
    return "just now"


# --- builders ---------------------------------------------------------------
def themed_table(**kwargs) -> Table:
    """A pre-themed rich Table (foam header, wake border, zebra rows).

    The caller adds columns/rows. Any kwargs override the defaults.
    """
    options = dict(
        show_header=True,
        header_style=S_HEADER,
        box=SIMPLE_HEAVY,
        border_style=S_BORDER,
        row_styles=S_ZEBRA,
        expand=True,
    )
    options.update(kwargs)
    return Table(**options)


def themed_panel(content, title: str = None, **kwargs) -> Panel:
    """A pre-themed rich Panel (wake border, hull fill, left-aligned title)."""
    options = dict(border_style=S_BORDER, style=S_PANEL_BG, padding=(1, 2))
    options.update(kwargs)
    title_markup = f"[bold {c('spray')}]{title}[/]" if title else None
    return Panel(content, title=title_markup, title_align="left", **options)


# --- run card (shared by CLI `show` and sillonlab Run.show) -----------------
def render_run_card(report: dict):
    """Builds the full run-detail panel from a `build_run_report` payload.

    Args:
        report (dict): The manifest from `silloncore.engine.build_run_report`.

    Returns:
        Panel: A rich renderable (params, results+sizes, figures w/ provenance,
            analyses, tags, notes, status, runtime).
    """
    table = themed_table(box=SIMPLE)
    table.add_column("Parameter", style=c("foam"))
    table.add_column("Value", style=S_VALUE)
    for key, value in report["parameters"].items():
        table.add_row(key, format_value(value))

    def _sized_line(name, info=None):
        suffix = f" ({human_size(info['bytes'])})" if info and info.get("bytes") is not None else ""
        return Text.assemble((f"  {name}", S_VALUE), (suffix, S_DIM))

    def _result_line(name, info):
        # Show the value for small/inline results; size for big arrays/artifacts.
        if "value" in info:
            return Text.assemble(
                (f"  {name}  ", S_VALUE), (format_value(info["value"]), S_ACCENT)
            )
        return _sized_line(name, info)

    lines = [
        Text.assemble(("Run id     ", S_LABEL), (short_id(report.get("uuid")), S_DIM)),
        Text.assemble(("Timestamp  ", S_LABEL), (str(report["date"]), S_DIM)),
        Text.assemble(("Status     ", S_LABEL), status_text(report["status"])),
        Text.assemble(("Runtime    ", S_LABEL), (str(report["runtime"] or "N/A"), S_DIM)),
        Text(""),
        table,
        Text(""),
        Text("Results", style=f"bold {c('foam')}"),
    ]

    result_items = {
        name: info
        for name, info in report["results"].items()
        if info.get("kind") in ("result", "artifact")
    }
    lines += [_result_line(n, i) for n, i in result_items.items()] or [Text("  none", style=S_DIM)]

    if report["figures"]:
        lines.append(Text("Figures", style=f"bold {c('wake')}"))
        for name, meta in report["figures"].items():
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

    if report["analyses"]:
        lines.append(Text("Analyses", style=f"bold {c('foam')}"))
        for name, meta in report["analyses"].items():
            comment = (meta.get("meta") or {}).get("comment")
            line = _sized_line(name, {"bytes": meta.get("size")})
            if comment:
                line.append(f"  ({comment})", style=S_DIM)
            lines.append(line)

    if report.get("parents"):
        parent_names = ", ".join(p.get("name", "?") for p in report["parents"])
        lines.append(Text.assemble(("Inherits   ", S_LABEL), (parent_names, c("wake"))))

    if report["tags"]:
        tag_text = Text("Tags       ", style=S_LABEL)
        for i, tag in enumerate(report["tags"]):
            if i:
                tag_text.append("  ", style=S_DIM)
            tag_text.append(f" {tag} ", style=f"{c('abyss')} on {c('ember')}")
        lines.append(tag_text)

    for note in report["notes"]:
        lines.append(Text(f"• {note}", style=f"italic {c('slate')}"))

    return themed_panel(Group(*lines), title=report["name"], expand=False)


def print_context(data: dict, project_name: str = "") -> None:
    """Prints an engine `get_project_context` payload (overview or specific)."""
    if data["mode"] == "overview":
        _print_overview(data["runs"], project_name)
    else:
        _print_specific(data["runs"])


def _print_overview(runs: list, project_name: str) -> None:
    table = themed_table(padding=(0, 2))
    table.add_column("ID", style=S_DIM)
    table.add_column("Run Name", style=f"bold {c('spray')}")
    table.add_column("When", style=S_DIM)
    table.add_column("Params", justify="center", style=c("wake"))
    table.add_column("Assets", justify="center", style=c("foam"))
    table.add_column("Status", justify="center")

    for run in runs:
        table.add_row(
            short_id(run.get("uuid", "")),
            str(run["name"]),
            relative_time(run["timestamp"]),
            str(run["param_count"]),
            str(run["asset_count"]),
            status_text(run["status"]),
        )

    subtitle = Text(
        f"{len(runs)} runs logged in the project", style=f"italic {c('ember')}"
    )
    console.print(
        themed_panel(Group(subtitle, Text(""), table), title=project_name or "Project")
    )


def _print_specific(runs: list) -> None:
    cards = []
    for run in runs:
        content = Group(
            Text.assemble(("Run Name  ", S_LABEL), (str(run["name"]), c("foam"))),
            Text.assemble(("Run id    ", S_LABEL), (short_id(run.get("uuid", "")), S_DIM)),
            Text.assemble(("Time      ", S_LABEL), (str(run["timestamp"]), S_DIM)),
            Text.assemble(
                ("Params    ", S_LABEL),
                (str(run["param_count"]), S_VALUE),
                ("   Assets  ", S_LABEL),
                (str(run["asset_count"]), c("foam")),
            ),
            Text.assemble(("Runtime   ", S_LABEL), (str(run.get("runtime", "N/A")), S_VALUE)),
            Text.assemble(("Language  ", S_LABEL), (str(run.get("language", "N/A")), S_VALUE)),
            Text.assemble(("Status    ", S_LABEL), status_text(run.get("status"))),
        )
        cards.append(themed_panel(content, title=run["name"], expand=False))
    console.print(Columns(cards, equal=True, expand=False))


def render_to_html(renderable, width: int = 100) -> str:
    """Render a rich renderable to standalone HTML (for Jupyter `_repr_html_`).

    Records into an off-screen console so nothing is also printed to stdout.
    """
    import io

    rec = Console(record=True, width=width, file=io.StringIO())
    rec.print(renderable)
    return rec.export_html(inline_styles=True)


__all__ = [
    "console",
    "c",
    "status_text",
    "human_size",
    "short_id",
    "format_value",
    "relative_time",
    "themed_table",
    "themed_panel",
    "render_run_card",
    "render_to_html",
    "print_context",
    "Columns",
    "Group",
    "Text",
]
