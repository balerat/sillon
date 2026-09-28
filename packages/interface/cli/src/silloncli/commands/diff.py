from silloncore.engine import diff as engine_diff, diff_across_runs
from silloncore.display import print_diff, print_diff_across, print_source_diff


def add_parser(command_subparser):
    diff_parser = command_subparser.add_parser(
        "diff",
        help="Compare two runs, or see what varies across a set of them.",
    )
    diff_parser.add_argument(
        "run_name",
        nargs="*",
        type=str,
        help="Two runs to compare. Omit when using --across.",
    )
    diff_parser.add_argument(
        "--across",
        nargs="*",
        metavar="KEY=VALUE",
        help="Summarise what varies across runs instead of comparing two "
             "(e.g. --across tag=sweep, or --across for the whole project).",
    )
    diff_parser.add_argument(
        "--source",
        action="store_true",
        help="Also print the unified source diff.",
    )
    diff_parser.add_argument(
        "--max-bytes",
        type=int,
        default=None,
        help="Largest result to load for comparison (default 64MB). Bigger "
             "results are compared by shape and dtype only.",
    )


def _parse_filters(pairs):
    """`tag=sweep status=SUCCESS` into query kwargs."""
    tags, fields = [], {}
    for pair in pairs or []:
        if "=" not in pair:
            print(f"⚠ Ignoring '{pair}': expected KEY=VALUE.")
            continue
        key, value = pair.split("=", 1)
        if key in ("tag", "tags"):
            tags.append(value)
        else:
            fields[key] = value
    query = {}
    if tags:
        query["has_tag"] = tags
    if fields:
        query["fields"] = fields
    return query


def command(engine, storage_root, args):
    """CLI Diff Command Handler.

    Two modes, because there are two questions. Comparing a pair answers "these
    disagree, why?"; --across answers "what was this sweep varying?", which is
    what you need when you come back to it later.
    """
    if args.get("across") is not None:
        result = diff_across_runs(engine, **_parse_filters(args["across"]))
        print_diff_across(result)
        return result

    names = args.get("run_name") or []
    if len(names) != 2:
        print("✖ Error: diff needs exactly two runs, or --across to summarise a set.")
        return None

    try:
        result = engine_diff(engine, storage_root, names[0], names[1], args.get("max_bytes"))
    except LookupError as e:
        print(f"✖ Error: {e}")
        return None

    print_diff(result)
    if args.get("source"):
        print_source_diff(result["code"]["source_diff"])
    return result
