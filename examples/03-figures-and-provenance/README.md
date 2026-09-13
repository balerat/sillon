# 03 — Figures and provenance

The two things that make sillon more than a metrics logger.

```bash
python run.py
sillon show baseline -f     # the figure and the data it was built from
sillon lineage refined      # ↑ parent / ↓ children
```

**Figure provenance.** `log_figure(fig, used=["coef", "degree"])` stores the plot
*and* the names of the values that produced it. `sillon show -f` renders it as:

```
fit  ← built from: coef, degree
```

That answers the question you will actually have later — *which data made this
plot?* — without you having to remember.

**Lineage.** `inherit="baseline"` records that one run derives from another.
Nothing is copied; it is a queryable edge:

```python
import sillonlab as sl

project = sl.load_project(".")
refined = project.get("refined")

print(refined.parent_links())                 # [{'uuid': ..., 'name': 'baseline'}]
print(project.get("baseline").children().list())  # ['refined']
```

**Tracing a file back to its run.** If you find a figure or artifact on disk and
no longer know where it came from:

```bash
sillon whose path/to/that/file.png
```
