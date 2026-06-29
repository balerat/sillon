"""Rich rendering for sillonlab — thin wrappers over the shared theme.

The palette, builders, and the run-card renderer live in
`silloncore.display` so the CLI and the analysis library look identical. This
module only adapts `Run` / `RunCollection` / engine payloads to those builders.
"""

from silloncore.display import (
    console,
    c,
    status_text,
    relative_time,
    short_id,
    themed_table,
    render_run_card,
    print_context,  # re-exported: overview/specific renderer lives in silloncore.display
    S_DIM,
)


def print_run(run) -> None:
    """Pretty-prints a single `Run` as a detail card."""
    console.print(render_run_card(run.manifest()))


def print_run_table(runs) -> None:
    """Pretty-prints a `RunCollection` as a summary table."""
    table = themed_table(pad_edge=False)
    table.add_column("ID", style=S_DIM)
    table.add_column("Run Name", style=f"bold {c('spray')}")
    table.add_column("When", style=S_DIM)
    table.add_column("Params", justify="center", style=c("wake"))
    table.add_column("Results", justify="center", style=c("foam"))
    table.add_column("Tags", style=c("ember"))
    table.add_column("Status", justify="center")

    for run in runs:
        params = run.parameters  # forces the snapshot to load (populates run.uuid)
        table.add_row(
            short_id(run.uuid or ""),
            run.name,
            relative_time(run.timestamp),
            str(len(params)),
            str(len(run.results)),
            ", ".join(run.tags),
            status_text(run.status),
        )

    console.print(table)
