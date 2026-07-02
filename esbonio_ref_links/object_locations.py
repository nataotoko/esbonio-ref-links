"""Record source locations for ``std:label`` / ``std:term`` objects in
esbonio's objects database.

esbonio's sphinx agent only records locations for ``nodes.target`` elements
(``esbonio/sphinx_agent/handlers/domains.py``).  Labels registered directly
with the std domain -- e.g. by ``sphinx.ext.autosectionlabel`` or glossary
terms -- carry no ``location``, so ``textDocument/definition`` (and the
document links produced by the companion server module
``esbonio_ref_links.document_links``) cannot point at the exact line.  This
extension fills those locations in after each build.

Positions are read from the pickled doctrees (``env.get_doctree``), so the
extension also works for incremental builds where unchanged documents never
pass through ``doctree-read`` in the current process.

Usage (``conf.py``)::

   extensions = [
       ...,
       "esbonio_ref_links.object_locations",
   ]

The module must be importable by the Python environment that runs the Sphinx
build (``esbonio.sphinx.pythonCommand``).  When the docs are built outside of
esbonio's sphinx agent (plain ``sphinx-build``), the extension does nothing.
"""

from __future__ import annotations

import typing

from sphinx.util import logging

if typing.TYPE_CHECKING:
    from typing import Any

    from sphinx.application import Sphinx

logger = logging.getLogger(__name__)

__version__ = "0.1.0"


def setup(app: Sphinx):
    # Must run after esbonio's DomainObjects.commit, which is connected to
    # build-finished at the default priority (500) and rewrites the whole
    # objects table.
    app.connect("build-finished", record_locations, priority=999)
    return {
        "version": __version__,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }


def record_locations(app: Sphinx, exc: Exception | None) -> None:
    if exc is not None:
        return

    if (esbonio := getattr(app, "esbonio", None)) is None:
        return  # not building through esbonio's sphinx agent

    try:
        from esbonio.sphinx_agent import types
        from esbonio.sphinx_agent.util import as_json
    except ImportError:
        logger.warning(
            "esbonio_ref_links.object_locations: esbonio.sphinx_agent is not importable, "
            "skipping"
        )
        return

    env = app.env
    std = env.get_domain("std")

    # (objtype, object name) -> (docname, node id)
    targets: dict[tuple[str, str], tuple[str, str]] = {}
    for name, (docname, node_id, _sectname) in std.labels.items():
        targets[("label", name)] = (docname, node_id)
    for name, (docname, node_id) in std.anonlabels.items():
        targets.setdefault(("label", name), (docname, node_id))
    for (objtype, name), (docname, node_id) in std.objects.items():
        if objtype == "term":
            targets[("term", name)] = (docname, node_id)

    db = esbonio.db.db  # sqlite3.Connection managed by the agent
    rows = db.execute(
        "SELECT rowid, name, objtype FROM objects "
        "WHERE project IS NULL AND domain = 'std' "
        "AND objtype IN ('label', 'term') AND location IS NULL"
    ).fetchall()

    doctrees: dict[str, Any] = {}
    updates: list[tuple[str, int]] = []

    for rowid, name, objtype in rows:
        if (entry := targets.get((objtype, name))) is None:
            continue

        docname, node_id = entry
        if docname not in env.all_docs:
            continue  # generated documents (genindex, search, ...) have no doctree

        if (found := _find_location(app, doctrees, docname, node_id)) is None:
            continue

        source, line = found
        location = types.Location(
            uri=str(types.Uri.for_file(source)),
            range=types.Range(
                start=types.Position(line=line, character=0),
                end=types.Position(line=line + 1, character=0),
            ),
        )
        updates.append((as_json(location), rowid))

    if updates:
        db.executemany("UPDATE objects SET location = ? WHERE rowid = ?", updates)
        db.commit()

    logger.info(
        "esbonio_ref_links.object_locations: recorded %d object location(s)", len(updates)
    )


def _find_location(
    app: Sphinx, doctrees: dict[str, Any], docname: str, node_id: str
) -> tuple[str, int] | None:
    """Return ``(source path, 0-based line)`` for the node with the given id."""
    if docname not in doctrees:
        try:
            doctrees[docname] = app.env.get_doctree(docname)
        except Exception:
            logger.warning(
                "esbonio_ref_links.object_locations: unable to load doctree for %r",
                docname,
                exc_info=True,
            )
            doctrees[docname] = None

    if (doctree := doctrees[docname]) is None:
        return None

    if (node := doctree.ids.get(node_id)) is None:
        return None

    # The node itself often has no line info (e.g. section elements); take the
    # first descendant that does.
    for candidate in node.findall():
        if candidate.line is not None:
            source = candidate.source or doctree.get("source")
            if source is None:
                return None
            return str(source), _adjusted_line(candidate)

    return None


def _adjusted_line(node: Any) -> int:
    """Convert a docutils node line to a 0-based source line.

    docutils lines are 1-based, but measured quirks (docutils 0.22) require
    per-node-type corrections: section/title lines point at the *underline* of
    the heading, glossary term lines at the line *before* the term.
    """
    from docutils import nodes

    if isinstance(node, (nodes.section, nodes.title)):
        offset = 2
    elif isinstance(node, nodes.term):
        offset = 0
    else:
        offset = 1

    return max(node.line - offset, 0)
