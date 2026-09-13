# 01 — Quickstart

One run, logged and stored.

```bash
python run.py
sillon context        # the project overview
sillon show my_fit    # this run in detail
```

Read it back in Python:

```python
import sillonlab as sl

run = sl.load_project(".").get("my_fit")
print(run.parameters)          # {'degree': 1, 'n_points': 100}
print(run.load_result("coef")) # the array, read back from HDF5
```

Run the script again and the second run is named `my_fit_2` — sillon never
overwrites a run.
