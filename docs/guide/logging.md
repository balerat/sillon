# Logging runs

Everything in `sillonpy`, the client you import inside a simulation script.

```python
import sillonpy as sp
```

## Opening a run

### `track_run` — the recommended form

A context manager. Opens a run and seals it on the way out, including when the
block raises.

```python
with sp.track_run(run_name="my_fit", project_name="demo", author="you"):
    sp.log_param("degree", 1)
```

Use it in a loop for a sweep — each iteration is its own run:

```python
for degree in range(1, 6):
    with sp.track_run(project_name="sweep"):
        sp.log_param("degree", degree)
        ...
```

### `init` — for a script that is one run

```python
sp.init(run_name="my_fit", project_name="demo")
sp.log_param("degree", 1)
# sealed automatically when the interpreter exits
```

Call `sp.force_dump()` to seal it early, for instance before starting a second
run in the same script.

All arguments are optional:

| Argument | Default |
|---|---|
| `run_name` | a generated name, unique in the project |
| `project_name` | empty |
| `project_path` | the current directory |
| `author`, `organisation` | empty |
| `inherit` | no parent — see [Provenance](provenance.md) |

### `@track` — logging a function's call

Records a decorated function's arguments, duration and return value under
generated keys. Handy for quick instrumentation, noisy for a real experiment:

```python
@sp.track
def simulate(alpha, beta):
    return alpha * beta
```

## Logging values

### Parameters — what you chose

```python
sp.log_param("degree", 3)                       # one
sp.log_param({"degree": 3, "solver": "lu"})     # a dict
sp.log_param(degree=3, solver="lu")             # keywords
```

### Results — what came out

```python
sp.log_result("rmse", 0.043)
sp.log_result("field", big_array)      # offloaded to HDF5 automatically
```

Large arrays are staged to disk and handed to the daemon without ever being
serialised into the message, so logging a gigabyte costs you a file write, not
memory.

### Artifacts — files you produced

```python
sp.log_result("mesh", path="out/mesh.vtk")                    # copied into the store
sp.log_result("scratch", path="tmp/big.dat", save_result=False)  # path recorded only
```

`save_result=False` records the path and its hash without copying the bytes —
right for something huge that already lives somewhere durable.

### Figures

```python
fig, ax = plt.subplots()
ax.plot(x, y)

sp.log_figure(fig, name="fit", used=["coef", "degree"],
              caption="Linear fit over the noisy sample")
```

`used=` is the part worth using. It records which logged values produced the
plot, so `sillon show my_fit -f` can tell you later:

```text
fit  ← built from: coef, degree
```

You can log an existing image instead:

```python
sp.log_figure(path="figures/fit.png", name="fit")
```

### Metadata, tags and notes

```python
sp.add_metadata("solver_version", "4.2")
sp.add_metadata({"cluster": "atlas", "queue": "long"})

sp.add_tag("baseline")
sp.add_tag("gpu", "overnight")          # several at once
sp.add_note("Re-ran after fixing the boundary condition")
```

`log_metadata` is an alias of `add_metadata`.

Some metadata is recorded for you on every run: hostname, working directory,
the source of your main script, the imported modules, the runtime, and the
final status.

## What types can I log?

Anything JSON-serialisable, plus numpy arrays and scalars, complex numbers and
`Path` objects. Arrays go to HDF5, the rest inline.

A custom object will be refused with a message naming the type:

```text
TypeError: Object of type Simulation is not JSON serializable.
Convert it to a dict, list, or string before logging.
```

## When something goes wrong

Failed log calls **raise**. If the daemon rejects a command, your script hears
about it rather than continuing with an incomplete record:

```text
Exception: UnknownCommand: no_such_command
```

That is deliberate — a silently dropped value would mean a run that claims data
it does not have. See [Troubleshooting](troubleshooting.md).

## Multiple runs in one script

```python
for config in configs:
    with sp.track_run(project_name="sweep"):
        ...
```

`track_run` is the simple answer. With `init`, seal each run with
`sp.force_dump()` before starting the next.

## Logging to another directory

```python
sp.init(project_path="/scratch/experiments/run-42")
```

Handy on a cluster where the job runs somewhere other than your project folder.
