"""Code versioning must track what the program does, not how it is written.

The motivating complaint: hashing source text reports a new version when you
change a tuned constant, so it cannot answer "which runs used the buggy code?".
Every test here is a case of "these two runs are / are not comparable".
"""

import textwrap

from silloncommon.codeversion import (
    ast_hash,
    compute_version,
    hash_file_source,
    logic_hash,
    short,
    source_hash,
)

BASE = textwrap.dedent(
    """
    import numpy as np

    N = 5

    def hamiltonian(kinetic, potential):
        return kinetic - potential

    def run():
        return hamiltonian(np.zeros(N), np.ones(N))
    """
)


def _variant(**edits):
    src = BASE
    for old, new in edits.items():
        src = src.replace(old.replace("__", " "), new)
    return src


# ==========================================
#        the objection this exists for
# ==========================================


def test_changing_a_constant_keeps_the_logic_version():
    """N = 5 -> N = 4 is a tuned value, not a code change."""
    tuned = BASE.replace("N = 5", "N = 4")

    assert logic_hash(tuned) == logic_hash(BASE), "a tuned constant changed the logic hash"
    # ...but the coarser levels still see it, which is how the CLI can report
    # "same logic, 1 constant differs".
    assert ast_hash(tuned) != ast_hash(BASE)
    assert source_hash(tuned) != source_hash(BASE)


def test_changing_a_string_constant_keeps_the_logic_version():
    src = BASE.replace("import numpy as np", "import numpy as np\nLABEL = 'a'")
    tweaked = src.replace("LABEL = 'a'", "LABEL = 'b'")
    assert logic_hash(tweaked) == logic_hash(src)


# ==========================================
#          what must still register
# ==========================================


def test_changing_an_operator_changes_the_logic_version():
    """The sign error: this is exactly what the feature must catch."""
    fixed = BASE.replace("kinetic - potential", "kinetic + potential")
    assert logic_hash(fixed) != logic_hash(BASE)


def test_adding_a_statement_changes_the_logic_version():
    changed = BASE.replace("    return run()", "    pass\n    return run()")
    changed = BASE.replace(
        "def run():", "def run():\n        np.seterr(all='raise')"
    )
    assert logic_hash(changed) != logic_hash(BASE)


def test_renaming_a_function_changes_the_logic_version():
    renamed = BASE.replace("hamiltonian", "H")
    assert logic_hash(renamed) != logic_hash(BASE)


# ==========================================
#          what must be invisible
# ==========================================


def test_comments_and_formatting_do_not_change_the_ast_version():
    noisy = BASE.replace(
        "def hamiltonian(kinetic, potential):",
        "# the Hamiltonian\n\n\ndef hamiltonian(kinetic,   potential):",
    )
    assert ast_hash(noisy) == ast_hash(BASE), "a comment changed the ast hash"
    assert logic_hash(noisy) == logic_hash(BASE)
    # only the byte-level hash notices
    assert source_hash(noisy) != source_hash(BASE)


def test_identical_source_hashes_identically():
    assert hash_file_source(BASE) == hash_file_source(BASE)


# ==========================================
#              resilience
# ==========================================


def test_unparseable_source_still_gets_a_stable_hash():
    """A syntax error must not blow up in the middle of logging a run."""
    broken = "def f(:\n  pass"
    assert logic_hash(broken) == source_hash(broken)
    assert logic_hash(broken) == logic_hash(broken)


# ==========================================
#          combining several files
# ==========================================


def test_version_covers_every_file():
    v = compute_version({"main.py": BASE, "lattice/ham.py": BASE})
    assert set(v["files"]) == {"main.py", "lattice/ham.py"}
    assert v["logic_version"] and v["ast_version"] and v["source_version"]


def test_editing_an_imported_module_changes_the_version():
    """The point of including custom modules: a change in your own library counts."""
    before = compute_version({"main.py": BASE, "lattice/ham.py": BASE})
    after = compute_version(
        {"main.py": BASE, "lattice/ham.py": BASE.replace("kinetic - potential", "kinetic + potential")}
    )
    assert after["logic_version"] != before["logic_version"]
    # and it names which file moved
    assert after["files"]["main.py"] == before["files"]["main.py"]
    assert after["files"]["lattice/ham.py"] != before["files"]["lattice/ham.py"]


def test_tuning_a_constant_in_a_module_keeps_the_version():
    before = compute_version({"main.py": BASE, "lattice/ham.py": BASE})
    after = compute_version(
        {"main.py": BASE, "lattice/ham.py": BASE.replace("N = 5", "N = 4")}
    )
    assert after["logic_version"] == before["logic_version"]
    assert after["source_version"] != before["source_version"]


def test_version_is_independent_of_import_order():
    a = compute_version({"main.py": BASE, "lattice/ham.py": BASE})
    b = compute_version({"lattice/ham.py": BASE, "main.py": BASE})
    assert a["logic_version"] == b["logic_version"]


def test_adding_a_module_changes_the_version():
    one = compute_version({"main.py": BASE})
    two = compute_version({"main.py": BASE, "extra.py": "x = 1\n"})
    assert one["logic_version"] != two["logic_version"]


def test_short_is_display_only():
    v = compute_version({"main.py": BASE})
    assert len(short(v["logic_version"])) == 6
    assert v["logic_version"].startswith(short(v["logic_version"]))
