# silloncli

The `sillon` command-line tool.

Every command is a thin renderer over `silloncore.engine`, which returns plain
data — that is why the CLI and `sillonlab` never disagree, and why a new output
format is cheap to add.

- `main.py` — argument parsing and the command table
- `commands/` — one module per command, each with `add_parser` and `command`

Full documentation: [CLI reference](../../../docs/reference/cli.md)
