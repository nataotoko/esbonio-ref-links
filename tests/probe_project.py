#!/usr/bin/env python
"""Build a real Sphinx project through esbonio's agent machinery and report
std:label / std:term location coverage, plus optional name resolutions.

Unlike run_tests.py this imports esbonio_zed_links from the interpreter's
installed packages (not from the repo), so it also validates the install.

Run through tests/probe_project.sh. stderr = build output, stdout = report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--srcdir", required=True, help="directory with conf.py")
    parser.add_argument("--workdir", required=True, help="scratch build directory")
    parser.add_argument("names", nargs="*", help="object names to resolve")
    args = parser.parse_args()

    srcdir = pathlib.Path(args.srcdir).resolve()
    workdir = pathlib.Path(args.workdir).resolve()
    outdir = workdir / "out"
    doctreedir = workdir / "doctrees"

    # Activate the esbonio agent handlers (see run_tests.py).
    import sphinx.application

    sphinx.application.builtin_extensions += (
        "esbonio.sphinx_agent.handlers.files",
        "esbonio.sphinx_agent.handlers.domains",
    )
    from esbonio.sphinx_agent.app import Sphinx

    app = Sphinx(
        srcdir=str(srcdir),
        confdir=str(srcdir),
        outdir=str(outdir),
        doctreedir=str(doctreedir),
        buildername="html",
        status=sys.stderr,
        warning=sys.stderr,
        freshenv=True,
    )
    app.build()

    import sqlite3

    dbpath = outdir / "esbonio.db"
    db = sqlite3.connect(dbpath)
    rows = db.execute(
        "SELECT name, objtype, docname, location FROM objects "
        "WHERE project IS NULL AND domain = 'std' AND objtype IN ('label', 'term') "
        "ORDER BY objtype, name"
    ).fetchall()
    db.close()

    with_loc = sum(1 for r in rows if r[3] is not None)
    print(f"std:label / std:term rows: {len(rows)}  with location: {with_loc}")
    for name, objtype, docname, location in rows:
        line = json.loads(location)["range"]["start"]["line"] if location else "-"
        print(f"   {objtype:5} {name!r} doc={docname} line0={line}")

    if args.names:
        import esbonio_zed_links as ezl
        from esbonio.server.features.project_manager import Project

        async def resolve_names():
            project = Project(dbpath, None)
            try:
                for name in args.names:
                    result = await ezl.find_object(
                        project, ("std:label", "std:term"), name
                    )
                    print(f"resolve {name!r} -> {result}")
            finally:
                await project.close()

        asyncio.run(resolve_names())

    return 0


if __name__ == "__main__":
    sys.exit(main())
