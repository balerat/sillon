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

**Lineage, without declaring it.** The second run loads the first one's `coef`
through sillonlab before logging. That is a derivation, and sillon saw it — so
the parent edge is recorded with no `inherit=` anywhere. The edge even names the
item that passed between them.

Browsing does not count: listing runs or reading `.parameters` records nothing.
Use `sl.forget_reads()` to clear the slate in a long session, and `inherit=`
when the two halves happen in different processes.

It is a queryable edge either way:

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
sillon trace path/to/that/file.png
```
