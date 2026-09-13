"""Find the best runs of the sweep.

Run `python run.py` first.
"""

import sillonlab as sl

project = sl.load_project(".")

# Cheap filters (parameters, tags, status) run against the database first;
# heavy filters that need the array store run only on what survives.
candidates = project.query(tags="sweep", parameters={"ridge": lambda r: r == 0.0})
print(f"{len(candidates)} runs with no ridge penalty")

# Rank by a logged result and take the best three.
best = candidates.sort_by("rmse")[:3]
for rank, run in enumerate(best, 1):
    print(f"  {rank}. {run.name:24} degree={run.parameters['degree']}  "
          f"rmse={run.load_result('rmse'):.3f}")

# Everything as a table (needs pandas: pip install "sillon[analysis]").
try:
    print()
    print(project.query(tags="sweep").to_dataframe().head())
except ImportError:
    print("(install pandas to see the DataFrame view)")
