from silloncli.context import project_root
from silloncore.check import check_project, repair_project
from silloncore.display import print_check_result


def add_parser(command_subparser):
    check_parser = command_subparser.add_parser(
        "check", help="Report anything in this project that no longer adds up."
    )
    check_parser.add_argument(
        "--repair",
        action="store_true",
        help="Also apply the fixes that cannot lose anything.",
    )


def command(engine, storage_root, args):
    """CLI Check Command Handler"""
    if args.get("repair"):
        result = repair_project(engine, storage_root, project_root())
    else:
        result = check_project(engine, storage_root, project_root())
    print_check_result(result)
    return result
