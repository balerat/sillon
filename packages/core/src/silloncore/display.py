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
    "CRASHED": f"bold #E06C75 on {c('hull')}",
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
            info = meta.get("meta") or {}
            line = _sized_line(name, {"bytes": meta.get("size")})
            used = info.get("used") or []
            if used:
                line.append(f"  ← computed from: {', '.join(used)}", style=S_DIM)
            if info.get("comment"):
                line.append(f"  ({info['comment']})", style=S_DIM)
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


def print_projects(records: list) -> None:
    """Prints a `silloncore.projects.get_projects` payload.

    Projects whose directory is gone are shown dimmed rather than hidden, so an
    unmounted drive looks different from a project you never had.
    """
    table = themed_table(padding=(0, 2))
    table.add_column("Project", style=f"bold {c('spray')}")
    table.add_column("Runs", justify="center", style=c("wake"))
    table.add_column("Last activity", style=S_DIM)
    # The location is the answer to the question this command exists to ask, so
    # it wraps rather than being ellipsized away on a narrow terminal.
    table.add_column("Location", style=S_DIM, overflow="fold", ratio=1)

    missing = 0
    for record in records:
        if record["exists"]:
            name = Text(record["project_name"] or "(unnamed)")
            runs = "?" if record["run_count"] is None else str(record["run_count"])
            when = relative_time(record["last_activity"]) if record["last_activity"] else "—"
            location = Text(record["project_path"])
        else:
            missing += 1
            name = Text(record["project_name"] or "(unnamed)", style=S_DIM)
            runs = "—"
            when = "missing"
            location = Text(record["project_path"], style=S_DIM)
        table.add_row(name, runs, when, location)

    summary = f"{len(records)} projects registered on this machine"
    if missing:
        summary += f" — {missing} no longer on disk (sillon projects --prune)"
    subtitle = Text(summary, style=f"italic {c('ember')}")
    console.print(themed_panel(Group(subtitle, Text(""), table), title="Projects"))


def print_code_versions(groups: list) -> None:
    """Prints a `silloncore.engine.get_code_versions` payload."""
    table = themed_table(padding=(0, 2))
    table.add_column("Version", style=f"bold {c('spray')}")
    table.add_column("Runs", justify="center", style=c("wake"))
    table.add_column("First seen", style=S_DIM)
    table.add_column("Last seen", style=S_DIM)
    table.add_column("Constants", justify="center", style=S_DIM)
    table.add_column("Covers", style=S_DIM)

    unversioned = 0
    for group in groups:
        version = group["logic_version"]
        if not version:
            unversioned = group["run_count"]
            continue
        variants = group["constant_variants"]
        table.add_row(
            Text(short_id(version)),
            str(group["run_count"]),
            relative_time(group["first_seen"]) if group["first_seen"] else "—",
            relative_time(group["last_seen"]) if group["last_seen"] else "—",
            str(variants) if variants > 1 else "—",
            "entry script only" if group.get("partial") else "all code",
        )

    versioned = len([g for g in groups if g["logic_version"]])
    summary = f"{versioned} code version{'s' if versioned != 1 else ''} across this project"
    if unversioned:
        summary += f" — {unversioned} run(s) logged before code versioning"
    subtitle = Text(summary, style=f"italic {c('ember')}")
    console.print(themed_panel(Group(subtitle, Text(""), table), title="Code versions"))


def print_code_version_files(detail: dict) -> None:
    """Prints the per-file breakdown of one code version."""
    table = themed_table(padding=(0, 2))
    table.add_column("File", style=f"bold {c('spray')}", overflow="fold", ratio=1)
    table.add_column("Logic", style=S_DIM)
    table.add_column("Exact", style=S_DIM)

    for name, hashes in sorted(detail["files"].items()):
        table.add_row(
            Text(name),
            short_id(hashes.get("logic_hash", "")),
            short_id(hashes.get("source_hash", "")),
        )

    subtitle = Text(
        f"{detail['run_count']} run(s) used this version", style=f"italic {c('ember')}"
    )
    console.print(
        themed_panel(
            Group(subtitle, Text(""), table),
            title=f"version · {short_id(detail['logic_version'])}",
        )
    )


def _fmt_delta(pct):
    if pct is None:
        return ""
    sign = "+" if pct > 0 else ""
    return f"({sign}{pct:.2f}%)" if abs(pct) < 1000 else f"({sign}{pct:.0f}%)"


def _describe_value(summary: dict) -> str:
    """One-line description of a compared value."""
    if not summary:
        return "—"
    if summary.get("kind") == "scalar":
        return format_value(summary.get("value"))
    if summary.get("kind") == "array":
        shape = summary.get("shape")
        return f"{summary.get('dtype')} {tuple(shape) if shape else ''}"
    if summary.get("kind") in ("sequence", "mapping"):
        return f"{summary['kind']} ({summary.get('length')})"
    return "—"


def print_diff(result: dict) -> None:
    """Prints a `silloncore.engine.diff` payload."""
    a, b = result["runs"]
    console.rule(f"[bold {c('foam')}]{a['name']}  →  {b['name']}[/]")

    # --- parameters -------------------------------------------------------
    params = result["parameters"]
    if params["changed"] or params["added"] or params["removed"]:
        table = themed_table(padding=(0, 2))
        table.add_column("Parameter", style=f"bold {c('spray')}")
        table.add_column("From", style=S_DIM)
        table.add_column("To", style=c("foam"))
        table.add_column("Δ", style=c("ember"))

        for key, change in result["parameters"]["changed"].items():
            table.add_row(
                key,
                format_value(change["old"]),
                format_value(change["new"]),
                _fmt_delta(change["delta_pct"]),
            )
        for key in params["added"]:
            table.add_row(key, "—", "[#6FCF8E]added[/]", "")
        for key in params["removed"]:
            table.add_row(key, "[#E06C75]removed[/]", "—", "")

        subtitle = Text(
            f"{params['unchanged']} unchanged", style=f"italic {c('slate')}"
        )
        console.print(themed_panel(Group(table, Text(""), subtitle), title="Parameters"))
    else:
        console.print(f"[{c('slate')}]Parameters are identical.[/]")

    # --- code -------------------------------------------------------------
    code = result["code"]
    if not code["known"]:
        console.print(f"[{c('slate')}]Code version was not recorded for these runs.[/]")
    elif code["same_logic"] and not code["constants_differ"]:
        cosmetic = any(f["status"] == "cosmetic" for f in code["files"].values())
        note = " (comments or formatting only)" if cosmetic else ""
        console.print(
            f"\n[bold {c('ember')}]Code[/]  same logic "
            f"[{c('slate')}]{short_id(code['logic_version'][0] or '')}{note}[/]"
        )
    elif code["same_logic"]:
        differing = [n for n, f in code["files"].items() if f["status"] == "constants"]
        console.print(
            f"\n[bold {c('ember')}]Code[/]  same logic "
            f"[{c('slate')}]{short_id(code['logic_version'][0] or '')}[/] — "
            f"constants differ in {', '.join(differing)}"
        )
    else:
        moved = [n for n, f in code["files"].items() if f["status"] in ("changed", "added", "removed")]
        console.print(
            f"\n[bold #E06C75]Code[/]  logic changed — {', '.join(moved) or 'unknown files'}"
        )

    # --- results ----------------------------------------------------------
    results = result["results"]
    interesting = {n: r for n, r in results.items() if r["status"] != "same"}
    if interesting:
        table = themed_table(padding=(0, 2))
        table.add_column("Result", style=f"bold {c('spray')}")
        table.add_column("From", style=S_DIM)
        table.add_column("To", style=c("foam"))
        table.add_column("", style=c("ember"))

        for name, info in interesting.items():
            if info["status"] == "added":
                table.add_row(name, "—", "[#6FCF8E]added[/]", "")
            elif info["status"] == "removed":
                table.add_row(name, "[#E06C75]removed[/]", "—", "")
            elif info["status"] == "unknown":
                table.add_row(
                    name,
                    _describe_value(info["old"]),
                    _describe_value(info["new"]),
                    "too large to compare",
                )
            else:
                note = _fmt_delta(info["delta_pct"]) or {
                    "shape": "shape changed",
                    "dtype": "dtype changed",
                    "contents": "contents differ",
                }.get(info["reason"], "")
                table.add_row(
                    name,
                    _describe_value(info["old"]),
                    _describe_value(info["new"]),
                    note,
                )

        same = len(results) - len(interesting)
        subtitle = Text(f"{same} unchanged", style=f"italic {c('slate')}")
        console.print(themed_panel(Group(table, Text(""), subtitle), title="Results"))
    elif results:
        console.print(f"[{c('slate')}]Results are identical.[/]")

    # --- context ----------------------------------------------------------
    context = result["context"]
    if context["status"] or context["runtime"]:
        lines = []
        if context["status"]:
            lines.append(f"  status   {context['status'][0]} → {context['status'][1]}")
        if context["runtime"]:
            lines.append(f"  runtime  {context['runtime'][0]} → {context['runtime'][1]}")
        console.print(f"\n[bold {c('ember')}]Context[/]\n" + "\n".join(lines))


def print_source_diff(source_diff: str) -> None:
    """Prints the unified source diff of a `diff` payload."""
    from rich.syntax import Syntax

    if not source_diff.strip():
        console.print(f"[{c('slate')}]No source differences to show.[/]")
        return
    console.rule(f"[bold {c('wake')}]Source[/]")
    console.print(Syntax(source_diff, "diff", theme="monokai", line_numbers=False))


def print_diff_across(result: dict) -> None:
    """Prints a `silloncore.engine.diff_across_runs` payload."""
    if not result["run_count"]:
        console.print(f"[{c('slate')}]No runs matched.[/]")
        return

    lines = []
    if result["varying"]:
        for key, values in result["varying"].items():
            shown = ", ".join(format_value(v) for v in values[:6])
            if len(values) > 6:
                shown += f", … ({len(values)} values)"
            lines.append(Text.assemble(("  varying   ", S_LABEL), (f"{key}: ", c("foam")), (shown, S_DIM)))
    else:
        lines.append(Text("  every parameter is identical across these runs", style=S_DIM))

    if result["constant"]:
        held = ", ".join(sorted(result["constant"]))
        lines.append(Text.assemble(("  constant  ", S_LABEL), (held, S_DIM)))

    versions = result["logic_versions"]
    if len(versions) == 1:
        lines.append(Text.assemble(("  code      ", S_LABEL), (f"one version ({short_id(versions[0])})", S_DIM)))
    elif len(versions) > 1:
        lines.append(
            Text.assemble(
                ("  code      ", S_LABEL),
                (f"{len(versions)} versions — these runs are not all comparable", "bold #E06C75"),
            )
        )

    subtitle = Text(f"{result['run_count']} runs", style=f"italic {c('ember')}")
    console.print(themed_panel(Group(subtitle, Text(""), *lines), title="Across runs"))


def print_similar_runs(result: dict) -> None:
    """Prints a `silloncore.engine.find_similar_runs` payload."""
    matches = result["matches"]
    if not matches:
        console.print(f"[{c('slate')}]No other runs to compare against.[/]")
        return

    table = themed_table(padding=(0, 2))
    table.add_column("Match", justify="right", style=c("wake"))
    table.add_column("Run", style=f"bold {c('spray')}")
    table.add_column("Differences", style=S_DIM, overflow="fold", ratio=1)
    table.add_column("Code", justify="center", style=S_DIM)

    for match in matches:
        if match["changes"]:
            changes = ", ".join(
                f"{key} {format_value(old)}→{format_value(new)}"
                for key, (old, new) in list(match["changes"].items())[:4]
            )
            if len(match["changes"]) > 4:
                changes += f", … (+{len(match['changes']) - 4})"
        elif match["only_in_other"] or match["missing_here"]:
            # No *shared* key differs, but the two runs are not describing the
            # same thing -- saying "identical parameters" here would be a lie.
            changes = "different parameter set"
        else:
            changes = "identical parameters"

        extra = []
        if match["only_in_other"]:
            extra.append(f"+{len(match['only_in_other'])} extra")
        if match["missing_here"]:
            extra.append(f"−{len(match['missing_here'])} missing")
        if extra:
            changes += f"  [{', '.join(extra)}]"

        table.add_row(
            f"{match['score'] * 100:.0f}%",
            match["name"],
            changes,
            "same" if match["same_code"] else "—",
        )

    subtitle = Text(
        f"most like {result['run']}", style=f"italic {c('ember')}"
    )
    console.print(themed_panel(Group(subtitle, Text(""), table), title="Similar runs"))
