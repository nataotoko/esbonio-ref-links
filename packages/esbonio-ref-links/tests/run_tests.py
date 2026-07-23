#!/usr/bin/env python
"""Verify esbonio_ref_links (document_links / object_locations) against a
fixture project.

Run through tests/run_tests.sh with a python that has esbonio + sphinx
installed. stderr = progress/debug, stdout = result summary.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import shutil
import sqlite3
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT_DIR = HERE.parent / "src"
FIXTURE = HERE / "fixture"

failures: list[str] = []


def log(*args):
    print(*args, file=sys.stderr)


def check(cond, msg):
    if cond:
        log("PASS:", msg)
    else:
        failures.append(msg)
        log("FAIL:", msg)


def test_regexes(ezl):
    matches = list(ezl.HYPERLINK_REF.finditer("see term_, ok"))
    check(
        len(matches) == 1
        and matches[0].group("simple") == "term"
        and matches[0].group("anon") == "_",
        "simple reference matches",
    )

    check(
        not list(ezl.HYPERLINK_REF.finditer("dunder __init__ here")),
        "no match on __init__",
    )
    check(
        not list(ezl.HYPERLINK_REF.finditer("snake_case word")),
        "no match on snake_case",
    )

    matches = list(ezl.HYPERLINK_REF.finditer("a `Beta Section`_ b"))
    check(
        len(matches) == 1 and matches[0].group("text") == "Beta Section",
        "phrase reference matches",
    )

    matches = list(ezl.HYPERLINK_REF.finditer("a `other doc <other.rst>`__ b"))
    check(
        len(matches) == 1 and matches[0].group("anon") == "__",
        "anonymous embedded reference matches",
    )

    check(
        not list(ezl.HYPERLINK_REF.finditer("a :ref:`plain role` b")),
        "no match on a bare role target",
    )

    match = ezl.EXPLICIT_TARGET.match(".. _explicit-target:")
    check(
        match is not None
        and match.group("name") == "explicit-target"
        and match.group("refuri") == "",
        "explicit target without uri",
    )

    match = ezl.EXPLICIT_TARGET.match(".. _Python: https://www.python.org/")
    check(
        match is not None and match.group("refuri") == "https://www.python.org/",
        "explicit target with uri",
    )

    check(
        ezl.normalize_name("Alpha  Section") == "alpha section",
        "normalize_name lowers and collapses whitespace",
    )

    matches = list(ezl.CITATION_REF.finditer("see [CIT2002]_ for details"))
    check(
        len(matches) == 1 and matches[0].group("citelabel") == "CIT2002",
        "citation reference matches",
    )

    matches = list(ezl.CITATION_REF.finditer("see [1]_ for details"))
    check(
        len(matches) == 1 and matches[0].group("citelabel") is None,
        "manually numbered footnote is not a citation",
    )

    matches = list(ezl.CITATION_REF.finditer("see [#note]_ for details"))
    check(
        len(matches) == 1 and matches[0].group("citelabel") is None,
        "auto-numbered footnote is not a citation",
    )

    matches = list(ezl.CITATION_REF.finditer("see [#]_ for details"))
    check(
        len(matches) == 1 and matches[0].group("citelabel") is None,
        "anonymous auto-numbered footnote is not a citation",
    )

    matches = list(ezl.CITATION_REF.finditer("see [*]_ for details"))
    check(
        len(matches) == 1 and matches[0].group("citelabel") is None,
        "auto-symbol footnote is not a citation",
    )


def build_fixture(workdir: pathlib.Path) -> pathlib.Path:
    outdir = workdir / "out"
    doctreedir = workdir / "doctrees"
    for d in (outdir, doctreedir):
        if d.exists():
            shutil.rmtree(d)

    # Activate the esbonio agent handlers we need (they inject themselves via
    # sphinx.application.builtin_extensions). `files` fills the files table
    # (docname <-> uri), `domains` fills the objects table.
    import sphinx.application

    sphinx.application.builtin_extensions += (
        "esbonio.sphinx_agent.handlers.files",
        "esbonio.sphinx_agent.handlers.domains",
    )
    from esbonio.sphinx_agent.app import Sphinx

    app = Sphinx(
        srcdir=str(FIXTURE),
        confdir=str(FIXTURE),
        outdir=str(outdir),
        doctreedir=str(doctreedir),
        buildername="html",
        status=sys.stderr,
        warning=sys.stderr,
        freshenv=True,
    )
    app.build()

    return outdir / "esbonio.db"


def test_locations(dbpath: pathlib.Path):
    index_lines = (FIXTURE / "index.rst").read_text(encoding="utf-8").splitlines()

    def line_of(text: str) -> int:
        return next(i for i, line in enumerate(index_lines) if line.strip() == text)

    db = sqlite3.connect(dbpath)
    rows = db.execute(
        "SELECT name, objtype, docname, location FROM objects "
        "WHERE project IS NULL AND domain = 'std' AND objtype IN ('label', 'term')"
    ).fetchall()
    citation_rows = db.execute(
        "SELECT name, docname, location FROM objects "
        "WHERE project IS NULL AND domain = 'citation' AND objtype = 'label'"
    ).fetchall()
    db.close()

    log("std objects in db:")
    for name, objtype, docname, location in rows:
        loc_line = json.loads(location)["range"]["start"]["line"] if location else None
        log(f"   {objtype:5} {name!r:30} doc={docname} line={loc_line}")

    log("citation objects in db:")
    for name, docname, location in citation_rows:
        loc_line = json.loads(location)["range"]["start"]["line"] if location else None
        log(f"   citation {name!r:30} doc={docname} line={loc_line}")

    def loc_line(objtype: str, name: str):
        for name_, objtype_, _docname, location in rows:
            if objtype_ == objtype and name_ == name:
                return json.loads(location)["range"]["start"]["line"] if location else None
        return "<no row>"

    for name, heading in [
        ("index:alpha section", "Alpha Section"),
        ("index:beta section", "Beta Section"),
    ]:
        actual, expected = loc_line("label", name), line_of(heading)
        check(
            actual == expected,
            f"location of {name!r} (actual={actual}, expected={expected})",
        )

    for term in ["term", "仕様"]:
        actual, expected = loc_line("term", term), line_of(term)
        check(
            actual == expected,
            f"location of term {term!r} (actual={actual}, expected={expected})",
        )

    citation_entry = next(
        ((n, d, loc) for n, d, loc in citation_rows if n == "CIT2002"), None
    )
    check(citation_entry is not None, "citation:label object 'CIT2002' recorded in db")
    if citation_entry is not None:
        _, _citation_docname, citation_location = citation_entry
        actual = (
            json.loads(citation_location)["range"]["start"]["line"]
            if citation_location
            else None
        )
        expected = line_of(".. [CIT2002] A sample citation.")
        check(
            actual == expected,
            f"location of citation 'CIT2002' (actual={actual}, expected={expected})",
        )


async def resolution_tests(ezl, dbpath: pathlib.Path):
    from esbonio.server import Uri
    from esbonio.server.features.project_manager import Project

    index_lines = (FIXTURE / "index.rst").read_text(encoding="utf-8").splitlines()

    def line_of(text: str) -> int:
        return next(i for i, line in enumerate(index_lines) if line.strip() == text)

    # The converter is only used by Project.load_as, which these helpers
    # never call.
    project = Project(dbpath, None)
    try:
        result = await ezl.find_object(project, ("std:label",), "index:Alpha Section")
        expected_fragment = f"#L{line_of('Alpha Section') + 1}"
        check(
            result is not None and result[0].endswith(expected_fragment),
            f"find_object mixed-case label -> {result}",
        )

        result = await ezl.find_object(project, ("std:term",), "仕様")
        check(
            result is not None and "#L" in result[0],
            f"find_object term -> {result}",
        )

        result = await ezl.find_object(project, ("std:label",), "no-such-label")
        check(result is None, "find_object misses unknown label")

        result = await ezl.find_object(project, ezl.CITATION_OBJECT_TYPES, "CIT2002")
        expected_fragment = f"#L{line_of('.. [CIT2002] A sample citation.') + 1}"
        check(
            result is not None and result[0].endswith(expected_fragment),
            f"find_object citation label -> {result}",
        )

        result = await ezl.find_object(
            project, ezl.CITATION_OBJECT_TYPES, "no-such-citation"
        )
        check(result is None, "find_object misses unknown citation label")

        doc_uri = Uri.for_file(FIXTURE / "index.rst").resolve()

        result = await ezl.resolve_embedded(project, doc_uri, "other.rst")
        check(
            result is not None and result[0].endswith("other.rst"),
            f"resolve_embedded relative path -> {result}",
        )

        result = await ezl.resolve_embedded(project, doc_uri, "missing.rst")
        check(result is None, "resolve_embedded missing path -> None")

        result = await ezl.resolve_embedded(project, doc_uri, "/other.rst")
        check(
            result is not None,
            f"resolve_embedded source-dir absolute -> {result}",
        )

        local = ezl.scan_explicit_targets(
            (FIXTURE / "index.rst").read_text(encoding="utf-8").splitlines(True)
        )
        result = await ezl.resolve_named(project, doc_uri, local, "explicit-target")
        expected_fragment = f"#L{line_of('.. _explicit-target:') + 1}"
        check(
            result is not None
            and result[0].startswith(str(doc_uri))
            and result[0].endswith(expected_fragment),
            f"resolve_named local target -> {result}",
        )

        result = await ezl.resolve_named(project, doc_uri, local, "term")
        check(
            result is not None and "#L" in result[0],
            f"resolve_named glossary term -> {result}",
        )
    finally:
        await project.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir", required=True)
    args = parser.parse_args()
    workdir = pathlib.Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT_DIR))
    from esbonio_ref_links import document_links as ezl

    test_regexes(ezl)

    dbpath = build_fixture(workdir)
    check(dbpath.exists(), "esbonio.db created")
    if dbpath.exists():
        test_locations(dbpath)
        asyncio.run(resolution_tests(ezl, dbpath))

    print(f"{len(failures)} failure(s)")
    for failure in failures:
        print("FAIL:", failure)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
