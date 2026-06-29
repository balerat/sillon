import argparse

from silloncore.engine import get_run_details, get_run_snapshot, build_run_report
from silloncore.display import (
    console,
    themed_table,
    themed_panel,
    render_run_card,
    status_text,
    format_value,
    c,
    Group,
    Text,
)
from silloncore.display import S_LABEL, S_DIM, S_VALUE


class ShowAction(argparse.Action):
    """Key-filter flag that defaults to "everything" when given no values."""

    def __call__(self, parser, namespace, values, option_strings=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values if values else self.const)
        setattr(namespace, self.dest, items)


def add_parser(command_subparser):
    show_parser = command_subparser.add_parser(
        "show",
        help="Show a run's full card, or specific sections with flags.",
    )
    show_parser.add_argument(
        "run_name", nargs="*", type=str, help="The names or uuids (or uuid prefixes) of the runs."
    )
    # Key filters (optionally take specific keys; bare flag = all).
    show_parser.add_argument("-p", "--parameter", action=ShowAction, nargs="*", type=str,
                             const=["%all%"], default=None, help="Show parameters (optionally specific keys).")
    show_parser.add_argument("-r", "--result", action=ShowAction, nargs="*", type=str,
                             const=["%all%"], default=None, help="Show results (optionally specific keys).")
    show_parser.add_argument("-m", "--metadata", action=ShowAction, nargs="*", type=str,
                             const=["%all%"], default=None, help="Show metadata (optionally specific keys).")
    # Section toggles.
    show_parser.add_argument("-t", "--tag", action="store_true", help="Show tags.")
    show_parser.add_argument("-f", "--figure", action="store_true", help="Show figures (with provenance).")
    show_parser.add_argument("-A", "--analysis", action="store_true", help="Show analyses.")
    show_parser.add_argument("-n", "--note", action="store_true", help="Show notes.")


_KEY_FLAGS = ("parameter", "result", "metadata")
_SECTION_FLAGS = ("tag", "figure", "analysis", "note")


def _kv_table(title: str, rows) -> None:
    table = themed_table()
    table.add_column("Run", style=c("spray"))
    table.add_column(title, style=c("foam"))
    table.add_column("Value", style=S_VALUE)
    for row in rows:
        table.add_row(str(row.run_name), str(getattr(row, "key", "—")), format_value(row.value))
    console.print(table)


def _print_sections(report: dict, args: dict) -> None:
    """Render the tag/figure/analysis/note sections requested for one run."""
    lines = []
    if args.get("tag") and report["tags"]:
        tags = Text("Tags  ", style=S_LABEL)
        for i, tag in enumerate(report["tags"]):
            tags.append("  " if i else "")
            tags.append(f" {tag} ", style=f"{c('abyss')} on {c('ember')}")
        lines.append(tags)
    if args.get("figure") and report["figures"]:
        lines.append(Text("Figures", style=f"bold {c('wake')}"))
        for name, meta in report["figures"].items():
            used = ", ".join(meta.get("used") or [])
            prov = f"  ← built from: {used}" if used else ""
            lines.append(Text.assemble((f"  {name}", S_VALUE), (prov, S_DIM)))
    if args.get("analysis") and report["analyses"]:
        lines.append(Text("Analyses", style=f"bold {c('foam')}"))
        for name, meta in report["analyses"].items():
            comment = (meta.get("meta") or {}).get("comment")
            lines.append(Text.assemble((f"  {name}", S_VALUE),
                                       (f"  ({comment})" if comment else "", S_DIM)))
    if args.get("note") and report["notes"]:
        lines.append(Text("Notes", style=f"bold {c('foam')}"))
        lines += [Text(f"  • {note}", style=f"italic {c('slate')}") for note in report["notes"]]
    if lines:
        console.print(themed_panel(Group(*lines), title=report["name"], expand=False))


def command(engine, storage_root, args):
    """CLI Show Command Handler."""
    runs = args.get("run_name") or []
    if not runs:
        console.print(
            "[yellow]Specify a run (e.g. [b]sillon show my_run[/b]), "
            "or use [b]sillon context[/b] for an overview.[/]"
        )
        return None

    any_key = any(args.get(k) for k in _KEY_FLAGS)
    any_section = any(args.get(k) for k in _SECTION_FLAGS)

    # No flags → the full themed card for each run.
    if not (any_key or any_section):
        for name in runs:
            snapshot = get_run_snapshot(engine, name)
            if snapshot is None:
                console.print(f"[bold red]✖[/] Run '{name}' not found.")
                continue
            console.print(render_run_card(build_run_report(engine, storage_root, snapshot)))
        return None

    # Filtered mode: key filters as cross-run tables, sections per run.
    if any_key:
        data = get_run_details(
            engine, run_names=runs,
            params=args.get("parameter"), meta=args.get("metadata"), results=args.get("result"),
        )
        if data.get("parameter"):
            _kv_table("Parameter", data["parameter"])
        if data.get("metadata"):
            _kv_table("Metadata", data["metadata"])
        if data.get("result"):
            _kv_table("Result", data["result"])

    if any_section:
        for name in runs:
            snapshot = get_run_snapshot(engine, name)
            if snapshot is None:
                console.print(f"[bold red]✖[/] Run '{name}' not found.")
                continue
            _print_sections(build_run_report(engine, storage_root, snapshot), args)
    return None
