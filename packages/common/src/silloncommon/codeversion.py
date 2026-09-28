"""Versioning a run by what its code *does*, not by how it is written.

Hashing source text answers the wrong question. Changing a tuned constant
(``N = 5`` to ``N = 4``) rewrites the bytes without changing the program, and a
reformat or a new comment does the same — so a text hash reports a new version
for runs that are perfectly comparable, which makes it useless for the question
it exists to answer: *which of my runs used the code with the bug in it?*

So three hashes, each ignoring more and answering something different:

===============  =======================================  ==========================
level            ignores                                  answers
===============  =======================================  ==========================
``source_hash``  nothing                                  byte-identical?
``ast_hash``     comments, formatting, blank lines        did anything real change?
``logic_hash``   the above **+ every literal value**      did the *logic* change?
===============  =======================================  ==========================

The AST carries no comments and no formatting at all, so ``ast_hash`` gets those
for free. ``logic_hash`` goes further and rewrites every constant to a single
placeholder, so only the shape of the program survives.

A run's version covers the entry script **and** the user's own modules, combined
in :func:`compute_version`.
"""

import ast
import hashlib

__all__ = [
    "source_hash",
    "ast_hash",
    "logic_hash",
    "hash_file_source",
    "compute_version",
    "short",
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def short(digest: str, length: int = 6) -> str:
    """The display form of a hash. Full digests are unreadable in a table."""
    return (digest or "")[:length]


def source_hash(source: str) -> str:
    """Hash of the exact bytes. Changes on any edit at all."""
    return _sha256(source)


class _NormalizeLiterals(ast.NodeTransformer):
    """Rewrites every literal to one placeholder.

    This is what makes ``N = 5`` and ``N = 4`` hash alike: the assignment, its
    target and its shape are preserved, only the value is erased.
    """

    _PLACEHOLDER = "\x00const"

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        return ast.copy_location(ast.Constant(value=self._PLACEHOLDER), node)


def _dump(tree: ast.AST) -> str:
    # attributes=False: line and column numbers would reintroduce sensitivity
    # to formatting, which is the whole thing we are trying to ignore.
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def ast_hash(source: str) -> str:
    """Hash of the parsed structure: comments and formatting do not count.

    Falls back to :func:`source_hash` when the source does not parse, so a
    syntactically invalid or non-Python file still gets a stable identity
    instead of raising in the middle of logging a run.
    """
    try:
        return _sha256(_dump(ast.parse(source)))
    except SyntaxError:
        return source_hash(source)


def logic_hash(source: str) -> str:
    """Hash of the structure with every literal normalised away.

    Two runs whose only difference is a tuned constant share a logic hash; two
    runs where a statement changed do not.
    """
    try:
        tree = _NormalizeLiterals().visit(ast.parse(source))
        return _sha256(_dump(tree))
    except SyntaxError:
        return source_hash(source)


def hash_file_source(source: str) -> dict:
    """All three levels for one file."""
    return {
        "source_hash": source_hash(source),
        "ast_hash": ast_hash(source),
        "logic_hash": logic_hash(source),
    }


def compute_version(files: dict) -> dict:
    """Combine per-file hashes into one version for the run.

    Args:
        files (dict): ``{normalised module name: source text}``. The name is
            what identifies a file across machines, so it must already be
            project-relative — an absolute path would make the same code hash
            differently on another machine.

    Returns:
        dict: ``{"logic_version", "ast_version", "source_version", "files"}``,
            where ``files`` maps each name to its three hashes.

    The combined hash is taken over the **sorted** ``(name, hash)`` pairs rather
    than over concatenated text. That makes it independent of import order, and
    it keeps the per-file hashes available so a diff can say *which* module
    changed instead of only that something did.
    """
    per_file = {name: hash_file_source(source) for name, source in files.items()}

    def _combine(level: str) -> str:
        joined = "\n".join(
            f"{name}\x00{per_file[name][level]}" for name in sorted(per_file)
        )
        return _sha256(joined)

    return {
        "logic_version": _combine("logic_hash"),
        "ast_version": _combine("ast_hash"),
        "source_version": _combine("source_hash"),
        "files": per_file,
    }
