from silloncore.engine import get_run_snapshot, find_children
from silloncore.display import console, themed_panel, c, Group, Text
from silloncore.display import S_LABEL, S_DIM, S_VALUE


def add_parser(command_subparser):
    lineage_parser = command_subparser.add_parser(
        "lineage", help="Show a run's lineage: what it inherited from and what derives from it."
    )
    lineage_parser.add_argument(
        "run_name", type=str, help="The run name, uuid, or uuid prefix."
    )


def command(engine, storage_root, args):
    """CLI Lineage Command Handler."""
    snapshot = get_run_snapshot(engine, args["run_name"])
    if snapshot is None:
        console.print(f"[bold red]✖[/] Run '{args['run_name']}' not found.")
        return None

    parents = snapshot.get("parents") or []
    children = find_children(engine, snapshot["uuid"])

    lines = [Text.assemble(("run  ", S_LABEL), (snapshot["name"], f"bold {c('spray')}")), Text("")]

    lines.append(Text("Inherited from", style=f"bold {c('wake')}"))
    if parents:
        for p in parents:
            inherited = ", ".join(p.get("params") or [])
            suffix = f"  (params: {inherited})" if inherited else ""
            lines.append(Text.assemble((f"  ↑ {p.get('name')}", S_VALUE), (suffix, S_DIM)))
    else:
        lines.append(Text("  (none)", style=S_DIM))

    lines.append(Text("Used by", style=f"bold {c('foam')}"))
    if children:
        for ch in children:
            lines.append(Text(f"  ↓ {ch['name']}", style=S_VALUE))
    else:
        lines.append(Text("  (none)", style=S_DIM))

    console.print(themed_panel(Group(*lines), title=f"lineage · {snapshot['name']}", expand=False))
    return {"parents": parents, "children": children}
