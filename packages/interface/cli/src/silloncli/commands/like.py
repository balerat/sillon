from silloncore.engine import find_similar_runs
from silloncore.display import print_similar_runs


def add_parser(command_subparser):
    like_parser = command_subparser.add_parser(
        "like",
        help="Find the runs most similar to a given one.",
    )
    like_parser.add_argument(
        "run_name",
        type=str,
        help="The run to compare against (name, uuid, or uuid prefix).",
    )
    like_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="How many matches to show (default 10).",
    )


def command(engine, storage_root, args):
    """CLI Like Command Handler.

    "Did I do something close to this?" — ranked by how much of the
    configuration two runs share, which is more useful than an exact-match
    check that only fires on a perfect repeat.
    """
    try:
        result = find_similar_runs(engine, args["run_name"], args.get("limit", 10))
    except LookupError as e:
        print(f"✖ Error: {e}")
        return None

    print_similar_runs(result)
    return result
