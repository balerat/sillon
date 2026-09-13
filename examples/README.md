# Examples

Each folder is a self-contained sillon project. Run a script and it creates its
own `.sillon/` store next to itself — nothing is written outside the folder.

| Example | What it shows |
|---|---|
| [`01-quickstart`](01-quickstart/) | Log one run: parameters, a result, a tag. The 10-line version. |
| [`02-parameter-sweep`](02-parameter-sweep/) | Many runs in a loop with `track_run`, then query and rank them. |
| [`03-figures-and-provenance`](03-figures-and-provenance/) | Figures that record which data produced them, and run lineage. |

```bash
cd examples/01-quickstart
python run.py
sillon context
```

To start over, delete the `.sillon/` folder inside the example.
