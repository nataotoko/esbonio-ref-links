"""Extra ``textDocument/documentLink`` targets for LSP clients that interpret
line-number fragments on ``file://`` URIs (e.g. Zed).

Zed resolves ``file:///path#L<line>`` (and ``#L<line>:<col>``) fragments to an
in-file position when opening a document link (see Zed's
``crates/editor/src/hover_links.rs``, ``parse_uri_fragment_position``).  This
makes it possible to expose links that esbonio deliberately leaves out because
"the documentLink API doesn't support specific locations in a file"
(``esbonio/server/features/sphinx_support/roles.py``).

Load this module into the esbonio language server with::

   esbonio server --include esbonio_zed_links

The module must be importable by the Python environment esbonio runs in, e.g.
``pip install -e <zed-rst>/lsp`` into that environment.

Links provided (all resolved against the local Sphinx project):

- ``:ref:`` and any other role backed by esbonio's ``objects`` database
  (``std:label``, ``std:term``, ...).  Links point at the recorded object
  location when available -- see the companion Sphinx extension
  ``esbonio_object_locations`` -- and fall back to the top of the target
  document otherwise.  Roles that esbonio already links (``:doc:``,
  ``:download:``, intersphinx) are left untouched.
- Named hyperlink references (``name_``, ```phrase name`_``), resolved against
  explicit targets in the same document (``.. _name:``) first, then against
  the objects database (``std:label``, ``std:term``).
- Embedded-target references (```text <target>`__``), resolved as URLs or as
  paths relative to the current document (or to the project source directory
  for ``/absolute`` targets).  Links are only emitted for paths that exist.

Like esbonio's built-in features, detection is a line-based regex scan that
does not consult the doctree, so occurrences inside literal blocks may produce
false-positive links.  Name matching approximates docutils' normalization
(lower-casing is ASCII-only on the SQL side).

License: Apache-2.0 (same as the zed-rst repository this module ships with).

Attribution: the role-scanning / link-range arithmetic and the shape of the
objects-database queries are adapted from esbonio
(https://github.com/swyddfa/esbonio, ``esbonio/server/features/rst/roles.py``
and ``esbonio/server/features/sphinx_support/roles.py``), which is distributed
under the MIT License, Copyright (c) 2021 Alex Carney.
"""

from __future__ import annotations

import json
import pathlib
import re
import typing

from lsprotocol import types as lsp

from esbonio import server
from esbonio.server import Uri
from esbonio.server.features.project_manager import ProjectManager
from esbonio.server.features.roles import RolesFeature
from esbonio.sphinx_agent.types import RST_ROLE

if typing.TYPE_CHECKING:
    from esbonio.server.features.project_manager import Project

    ResolvedTarget = tuple[str, str | None] | None
    """A resolved link: ``(uri or url, tooltip)``."""


OBJECT_TYPES = ("std:label", "std:term")
"""Object types used to resolve named hyperlink references."""

INLINE_LITERAL = re.compile(r"``[^`]*``")

SIMPLENAME = r"(?:(?!_)\w)+(?:[-._+:](?:(?!_)\w)+)*"
"""docutils' "simple reference name": alphanumerics with isolated internal
punctuation (so ``__init__`` or trailing/leading underscores never match)."""

HYPERLINK_REF = re.compile(
    rf"""
    (?:
      `(?P<text>[^`]+)`                      # phrase reference
      |
      (?<![\w.+:-])(?P<simple>{SIMPLENAME})  # simple reference
    )
    (?P<anon>__|_)                           # named `_` / anonymous `__`
    (?![\w`])
    """,
    re.VERBOSE,
)

EMBEDDED_TARGET = re.compile(r"^(?P<text>.*?)\s*<(?P<target>[^<>]+)>$", re.DOTALL)

EXPLICIT_TARGET = re.compile(
    r"^\s*\.\.\s+_(?:`(?P<quoted>[^`]+)`|(?P<name>[^:`][^:]*)):\s*(?P<refuri>.*?)\s*$"
)

URL_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def normalize_name(name: str) -> str:
    """Approximation of docutils' ``fully_normalize_name``."""
    return " ".join(name.split()).lower()


def location_to_target(location: str) -> str:
    """Convert a serialized ``location`` value from the objects database into
    a link target with a 1-based line fragment."""
    loc = json.loads(location)
    line = loc["range"]["start"]["line"] + 1
    return f"{loc['uri']}#L{line}"


def scan_explicit_targets(lines: list[str]) -> dict[str, tuple[int, str]]:
    """Map normalized target name -> ``(0-based line, refuri)`` for every
    ``.. _name:`` line in the document."""
    targets: dict[str, tuple[int, str]] = {}

    for linum, line in enumerate(lines):
        if (match := EXPLICIT_TARGET.match(line)) is None:
            continue

        name = match.group("quoted") or match.group("name")
        if not name or name.startswith("_"):
            continue

        targets.setdefault(normalize_name(name), (linum, match.group("refuri")))

    return targets


async def find_object(
    project: Project, obj_types: tuple[str, ...] | list[str], name: str
) -> ResolvedTarget:
    """Look up ``name`` in the project's objects database.

    Rows with a recorded location win (line-precise target); otherwise fall
    back to the top of the object's document.  The name is matched verbatim
    first, then in normalized form (labels are stored normalized, but authors
    may write ``:ref:`` targets with the original capitalization).
    """
    if not obj_types:
        return None

    db = await project.get_db()
    placeholders = ", ".join("?" for _ in obj_types)
    query = (
        "SELECT name, docname, location FROM objects "  # noqa: S608
        f"WHERE printf('%s:%s', domain, objtype) IN ({placeholders}) "
        "AND project IS NULL AND (name = ? OR name = ?)"
    )
    cursor = await db.execute(query, (*obj_types, name, normalize_name(name)))
    rows = await cursor.fetchall()

    fallback = None
    for name_, docname, location in rows:
        if location is not None:
            return location_to_target(location), f"{name_} ({docname})"
        if fallback is None:
            fallback = (name_, docname)

    if fallback is not None:
        name_, docname = fallback
        if (uri := await project.docname_to_uri(docname)) is not None:
            return uri, f"{name_} ({docname})"

    return None


async def resolve_named(
    project: Project,
    doc_uri: Uri,
    local_targets: dict[str, tuple[int, str]],
    name: str,
) -> ResolvedTarget:
    """Resolve a named hyperlink reference (``name_`` / ```name`_``)."""
    if (local := local_targets.get(normalize_name(name))) is not None:
        linum, refuri = local
        if not refuri:
            return f"{doc_uri}#L{linum + 1}", None
        if URL_SCHEME.match(refuri) and not refuri.endswith("_"):
            return refuri, None
        # Indirect (``.. _a: b_``) or relative targets: fall through to the db.

    return await find_object(project, OBJECT_TYPES, name)


async def resolve_embedded(
    project: Project, doc_uri: Uri, target: str
) -> ResolvedTarget:
    """Resolve an embedded reference target (```text <target>`__``) as a URL
    or as a file path."""
    if URL_SCHEME.match(target):
        return target, None

    if (fs_path := doc_uri.fs_path) is None:
        return None

    doc_path = pathlib.Path(fs_path)
    if target.startswith("/"):
        # Interpret as relative to the project source directory, which is the
        # document's directory less one level per '/' in its docname.
        if (docname := await project.uri_to_docname(str(doc_uri))) is None:
            return None

        srcdir = doc_path.parent
        for _ in range(docname.count("/")):
            srcdir = srcdir.parent
        path = (srcdir / target.lstrip("/")).resolve()
    else:
        path = (doc_path.parent / target).resolve()

    if not path.exists():
        return None

    return str(Uri.for_file(path)), str(path)


def _overlaps(span: tuple[int, int], claimed: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(not (end <= s or e <= start) for s, e in claimed)


class ZedDocumentLinks(server.LanguageFeature):
    """documentLink support for ``:ref:``-style roles and hyperlink references."""

    def __init__(self, roles: RolesFeature, manager: ProjectManager, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.roles = roles
        self.manager = manager

    async def document_link(
        self, context: server.DocumentLinkContext
    ) -> list[lsp.DocumentLink] | None:
        if not (context.uri.path or "").endswith(".rst"):
            return None

        if (project := self.manager.get_project(context.uri)) is None:
            return None

        doc_uri = context.uri.resolve()
        local_targets = scan_explicit_targets(context.doc.lines)
        cache: dict = {}
        links: list[lsp.DocumentLink] = []

        for linum, line in enumerate(context.doc.lines):
            claimed = [m.span() for m in INLINE_LITERAL.finditer(line)]

            for match in RST_ROLE.finditer(line):
                if not match.group("target"):
                    continue
                # Keep the hyperlink-reference pass out of role targets, even
                # for roles we end up not linking.
                claimed.append(match.span())

                label = match.group("label")
                name = match.group("name")
                if not label or not name:
                    continue

                resolved = await self._role_link(context, project, name, label, cache)
                if resolved is None:
                    continue

                char = "<" if match.group("alias") is not None else "`"
                if (idx := match.group(0).find(f"{char}{label}")) < 0:
                    continue

                start = match.start() + idx + 1
                links.append(
                    self._make_link(context, resolved, linum, start, start + len(label))
                )

            for match in HYPERLINK_REF.finditer(line):
                if _overlaps(match.span(), claimed):
                    continue

                resolved, span = await self._reference_link(
                    project, doc_uri, local_targets, match, cache
                )
                if resolved is None or span is None:
                    continue

                links.append(self._make_link(context, resolved, linum, *span))

        return links or None

    def _make_link(
        self,
        context: server.DocumentLinkContext,
        resolved: tuple[str, str | None],
        linum: int,
        start: int,
        end: int,
    ) -> lsp.DocumentLink:
        target, tooltip = resolved
        return lsp.DocumentLink(
            target=target,
            tooltip=tooltip if context.tooltip_support else None,
            range=lsp.Range(
                start=lsp.Position(line=linum, character=start),
                end=lsp.Position(line=linum, character=end),
            ),
        )

    async def _role_link(
        self,
        context: server.DocumentLinkContext,
        project: Project,
        name: str,
        label: str,
        cache: dict,
    ) -> ResolvedTarget:
        key = ("role", name, label)
        if key in cache:
            return cache[key]

        resolved = None
        # Skip anything the built-in features already turn into a link
        # (:doc:, :download:, intersphinx) to avoid duplicate links.
        if await self.roles.resolve_target_link(context, name, label) is None:
            if obj_types := await self._role_obj_types(context, name):
                resolved = await find_object(project, obj_types, label)

        cache[key] = resolved
        return resolved

    async def _role_obj_types(
        self, context: server.DocumentLinkContext, name: str
    ) -> list[str]:
        """The local-project object types the given role can refer to."""
        if (role := await self.roles.get_role(context.uri, name)) is None:
            return []

        obj_types: list[str] = []
        for spec in role.target_providers:
            if spec.name != "objects":
                continue

            kwargs = spec.kwargs or {}
            if kwargs.get("projects") is not None:
                continue

            obj_types.extend(kwargs.get("obj_types") or [])

        return obj_types

    async def _named(
        self,
        project: Project,
        doc_uri: Uri,
        local_targets: dict[str, tuple[int, str]],
        name: str,
        cache: dict,
    ) -> ResolvedTarget:
        key = ("named", normalize_name(name))
        if key not in cache:
            cache[key] = await resolve_named(project, doc_uri, local_targets, name)
        return cache[key]

    async def _reference_link(
        self,
        project: Project,
        doc_uri: Uri,
        local_targets: dict[str, tuple[int, str]],
        match: re.Match,
        cache: dict,
    ) -> tuple[ResolvedTarget, tuple[int, int] | None]:
        anon = match.group("anon") == "__"

        if (name := match.group("simple")) is not None:
            if anon:
                # Anonymous non-embedded references need target ordering to
                # resolve; out of scope.
                return None, None
            resolved = await self._named(project, doc_uri, local_targets, name, cache)
            return resolved, match.span("simple")

        text = match.group("text")
        text_start = match.start("text")

        if (em := EMBEDDED_TARGET.match(text)) is not None:
            target = em.group("target")
            if em.group("text"):
                span = (text_start + em.start("text"), text_start + em.end("text"))
            else:
                span = (text_start + em.start("target"), text_start + em.end("target"))

            if target.endswith("_") and len(target.rstrip("_")) > 0:
                # Embedded alias to another target: `text <name_>`__
                resolved = await self._named(
                    project, doc_uri, local_targets, target.rstrip("_"), cache
                )
            else:
                key = ("embedded", target)
                if key not in cache:
                    cache[key] = await resolve_embedded(project, doc_uri, target)
                resolved = cache[key]

            return resolved, span

        if anon:
            return None, None

        resolved = await self._named(project, doc_uri, local_targets, text, cache)
        return resolved, match.span("text")


def esbonio_setup(
    esbonio: server.EsbonioLanguageServer,
    roles: RolesFeature,
    project_manager: ProjectManager,
):
    esbonio.add_feature(ZedDocumentLinks(roles, project_manager, esbonio))
