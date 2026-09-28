from silloncore.engine import (
    get_code_versions,
    get_code_version_files,
    backfill_code_versions,
)
from silloncore.display import print_code_versions, print_code_version_files


def add_parser(command_subparser):
    versions_parser = command_subparser.add_parser(
        "versions",
        help="Group runs by the version of the code that produced them.",
    )
    versions_parser.add_argument(
        "version",
        nargs="?",
        type=str,
        help="A version hash or prefix; omit to list every version.",
    )
    versions_parser.add_argument(
        "--backfill",
        action="store_true",
        help="Recover versions for runs logged before code versioning existed.",
    )
    versions_parser.add_argument(
        "--files",
        action="store_true",
        help="Show the per-file hashes of a version (implied when one is named).",
    )


def command(engine, storage_root, args):
    """CLI Versions Command Handler.

    A run's code version covers its entry script and the user's own modules,
    hashed so that a tuned constant does not read as a new version — the point
    being to answer "which of my runs used the code with the bug in it".
    """
    if args.get("backfill"):
        result = backfill_code_versions(engine, storage_root)
        print(
            f"✔ Recovered {result['updated']} version(s) across "
            f"{result['versions']} distinct code version(s)."
        )
        if result["skipped"]:
            print(f"  {result['skipped']} run(s) skipped — no source was recorded.")
        print("  These cover the entry script only; runs logged from now on also")
        print("  include your own modules.\n")

    version = args.get("version")
    if version:
        try:
            detail = get_code_version_files(engine, version)
        except LookupError as e:
            print(f"✖ Error: {e}")
            return None
        print_code_version_files(detail)
        return detail

    groups = get_code_versions(engine)
    print_code_versions(groups)
    return groups
