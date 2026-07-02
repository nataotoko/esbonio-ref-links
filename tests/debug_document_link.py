#!/usr/bin/env python
"""Reproduce RefLinksFeature.document_link() against a real esbonio.db.

Stubs the server/roles machinery just enough to run the full per-line scan,
so exceptions raised by the feature surface directly instead of being
swallowed by esbonio's per-feature error handling.

usage (via debug_document_link.sh): <python> <dbpath> <rstfile> [rstfile ...]
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
import sys


class StubDoc:
    def __init__(self, path: pathlib.Path):
        self.lines = path.read_text(encoding="utf-8").splitlines(keepends=True)


class StubServer:
    logger = logging.getLogger("debug")


class StubRoles:
    """Minimal RolesFeature: role lookup from the db, no built-in links."""

    def __init__(self, project):
        self.project = project

    async def resolve_target_link(self, context, name, label):
        return None  # pretend the built-in features linked nothing

    async def get_role(self, uri, name):
        role = await self.project.get_role(name)
        if role is None:
            role = await self.project.get_role(f"std:{name}")
        return role


class StubManager:
    def __init__(self, project):
        self.project = project

    def get_project(self, uri):
        return self.project


async def run(dbpath: str, files: list[str]) -> int:
    from lsprotocol import types as lsp
    from pygls.protocol import default_converter

    from esbonio_ref_links import document_links as ezl
    from esbonio.server import Uri
    from esbonio.server.feature import DocumentLinkContext
    from esbonio.server.features.project_manager import Project

    project = Project(dbpath, default_converter())
    feature = ezl.RefLinksFeature(StubRoles(project), StubManager(project), StubServer())

    status = 0
    try:
        for file in files:
            path = pathlib.Path(file).resolve()
            context = DocumentLinkContext(
                uri=Uri.for_file(path).resolve(),
                doc=StubDoc(path),
                capabilities=lsp.ClientCapabilities(),
            )
            print(f"=== {path.name}")
            try:
                links = await feature.document_link(context)
            except Exception:
                import traceback

                status = 1
                print("EXCEPTION:")
                traceback.print_exc(file=sys.stdout)
                continue

            for link in links or []:
                rng = link.range
                print(
                    f"   L{rng.start.line + 1}:{rng.start.character}-{rng.end.character}"
                    f" -> {link.target}"
                )
            print(f"   total: {len(links or [])}")
    finally:
        await project.close()

    return status


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    return asyncio.run(run(sys.argv[1], sys.argv[2:]))


if __name__ == "__main__":
    sys.exit(main())
