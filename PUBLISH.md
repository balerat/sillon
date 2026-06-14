# Publishing `sillon` to PyPI — what you need to do

Everything in the repo is ready: a single-distribution `pyproject.toml` (name `sillon`,
version `1.0.0`, Apache-2.0), a build that produces one wheel containing all five packages,
and two GitHub Actions workflows. This file lists the steps **only you can do** (browser /
account actions) plus how to test and release.

I already verified locally: `python -m build` succeeds, `twine check` passes, and the built
wheel installs into a clean virtualenv where `import sillonpy/sillonlab/...`, the `sillon` CLI,
the auto-spawned daemon, and a full log→read round-trip all work.

---

## 0. One thing to know about your current `pyenv/`

The `pyenv/` virtualenv in the repo was created in the *old* path, so its `pip`/`python`
shebangs are broken (use `pyenv/bin/python -m pip ...`, not `pyenv/bin/pip`). It's now in
`.gitignore` and not tracked — fine to keep locally, but for a clean dev setup prefer a fresh
venv: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.

---

## 1. Commit the cleanup (local, then push)

I untracked the build artifacts (`*.egg-info/`) from git and added `pyenv/` to `.gitignore`.
Review and commit:

```bash
git status
git add -A
git commit -m "Package as a single 'sillon' distribution; add CI + publish workflows"
git push origin main
```

Note: `.gitignore` currently also ignores `examples/`. Those files are still tracked from before.
If you want the examples visible on GitHub, remove the `examples/` line from `.gitignore`.
If you don't, run `git rm -r --cached examples/` and commit.

---

## 2. Test locally before publishing

```bash
# build the artifacts
python -m build                 # -> dist/sillon-1.0.0.tar.gz and .whl
python -m twine check dist/*    # metadata sanity check

# prove a clean install works (throwaway venv)
python -m venv /tmp/sillon-check
/tmp/sillon-check/bin/pip install dist/sillon-1.0.0-py3-none-any.whl
/tmp/sillon-check/bin/python -c "import sillonpy, sillonlab; print('ok')"
/tmp/sillon-check/bin/sillon --help   # run inside a project dir (one with a .sillon folder)
```

Run the test suite too: `make test` (or `pip install -e ".[dev]" && pytest ...`).

---

## 3. Configure PyPI Trusted Publishing (browser — do this once)

This lets GitHub Actions upload to PyPI with **no API token**.

### a) TestPyPI (for a dry run — recommended first)
1. Create/log in at <https://test.pypi.org>.
2. Go to **Your projects → Publishing** (or, since `sillon` doesn't exist yet there, use
   **Account → Publishing → Add a pending publisher**).
3. Add a **pending trusted publisher** with:
   - PyPI Project Name: `sillon`
   - Owner: `balerat`
   - Repository name: `sillon`
   - Workflow name: `publish.yml`
   - Environment name: `pypi`

### b) PyPI (the real index)
Same steps at <https://pypi.org> → **Account → Publishing → Add a pending publisher**, with the
exact same five values. (You said you already own the `sillon` name — if the project page
exists, add the trusted publisher under that project's **Settings → Publishing** instead.)

> The Owner/Repo/Workflow/Environment values **must match exactly** what's in
> `.github/workflows/publish.yml` (`environment: pypi`) and your GitHub repo
> `balerat/sillon`. If you rename any of them, update both places.

---

## 4. Create the `pypi` environment on GitHub (browser — once)

In the GitHub repo: **Settings → Environments → New environment**, name it `pypi`.
(Optional but nice: add yourself as a *required reviewer* so a release waits for your click.)

---

## 5. Release procedure (every release)

The workflow triggers on a pushed tag `v*`.

```bash
# 1. bump the version (single source of truth)
#    edit packages/common/src/silloncommon/__init__.py  ->  __version__ = "1.0.0"
#    (pyproject reads it automatically; keep the tag in sync with this value)

# 2. commit + tag + push
git add -A && git commit -m "Release v1.0.0"
git tag v1.0.0
git push origin main --tags
```

Pushing the tag runs **`.github/workflows/publish.yml`**, which builds the sdist+wheel and
uploads them to PyPI via trusted publishing. Watch it under the repo's **Actions** tab.

### Dry run on TestPyPI first (optional but recommended)
The default `publish.yml` targets real PyPI. To rehearse on TestPyPI, temporarily add
`repository-url: https://test.pypi.org/legacy/` under the `with:` of the
`pypa/gh-action-pypi-publish` step (and make sure the TestPyPI pending publisher from step 3a
exists), push a pre-release tag like `v1.0.0rc1`, then:

```bash
pip install -i https://test.pypi.org/simple/ sillon
```

Remove the `repository-url` line again before the real release.

---

## 6. After publishing

```bash
python -m venv /tmp/verify && source /tmp/verify/bin/activate
pip install sillon                 # from real PyPI
pip install "sillon[analysis]"     # if you want pandas / to_dataframe()
sillon --help
```

Then walk through the README quickstarts. Done — users can now `pip install sillon`.

---

## Decisions baked in (change if you want)

- **Version is single-sourced** from `packages/common/src/silloncommon/__init__.py:__version__`.
  Bump it there only; `pyproject.toml` reads it via `tool.setuptools.dynamic`.
- **`requires-python = ">=3.11"`.** The test workflow runs 3.11/3.12/3.13; if 3.11 fails, raise
  the floor in `pyproject.toml`.
- **Console command is `sillon`** (renamed from `sil`). The old `requirements.txt` (mkdocs only)
  is now redundant — those deps live in the `docs` extra (`pip install -e ".[docs]"`); delete it
  whenever you like, but check `.github/workflows/deploy-docs.yml` doesn't reference it first.
- **Author email/URLs**: `pyproject.toml` still has a placeholder email for one author and points
  URLs at `github.com/balerat/sillon` — adjust if the repo owner/name differs.
