# esbonio-zed-links

Line-precise LSP document links for [esbonio](https://github.com/swyddfa/esbonio) +
[Zed](https://zed.dev/): two Python modules that make `:ref:` roles and reST
hyperlink references clickable, jumping to the exact source line via
`file:///...#L<line>` URI fragments (which Zed resolves to in-file positions).

- **`esbonio_zed_links`** — an esbonio server module (loaded with `--include`)
  that emits document links for `:ref:`-style roles (resolved through esbonio's
  objects database) and for hyperlink references (`name_`, `` `phrase`_ ``,
  `` `text <path-or-url>`__ ``, `.. _name:` targets in the same file). Roles
  esbonio already links (`:doc:`, `:download:`, intersphinx) are left untouched.
- **`esbonio_object_locations`** — a Sphinx extension that records the exact
  source line of `std:label` / `std:term` objects (autosectionlabel labels,
  glossary terms) into esbonio's database after each build. Without it the
  links above still land at the top of the target document; it also makes
  esbonio's go-to-definition line-precise for those objects. Outside an
  esbonio-driven build (plain `sphinx-build`) it does nothing.

## Setup

Assuming esbonio and Sphinx run from your project venv:

1. Install this package into that venv (both modules ship in one wheel):

   ```
   uv pip install <path-or-url-to-this-repo>
   ```

2. In your project's `.zed/settings.json`:

   ```json
   {
     "lsp": {
       "esbonio": {
         "binary": {
           "path": ".venv/Scripts/esbonio.exe",
           "arguments": ["server", "--include", "esbonio_zed_links"]
         },
         "settings": {
           "esbonio": {
             "sphinx": {
               "pythonCommand": [".venv/Scripts/python.exe"]
             }
           }
         }
       }
     }
   }
   ```

   (POSIX layout uses `.venv/bin/`.) Zed applies `lsp.<id>.binary` overrides to
   extension-provided servers — verified empirically, though undocumented; the
   [zed-rst](https://github.com/nataotoko/zed-rst) extension >= 0.0.4 also
   honors them itself as a safeguard.

3. In your `conf.py`:

   ```python
   extensions = [
       # ...
       "esbonio_object_locations",
   ]
   ```

## Caveats

Like esbonio's built-in features, link detection is a line-based regex scan, so
examples inside literal blocks may be linkified (false positives). Links
reflect the last build — new labels appear after a rebuild. Line-precise jumps
require a client that resolves URI fragments on file links; Zed does, other
editors may silently ignore them. Zed only re-requests document links on edit,
buffer reopen, or language-server restart, so a buffer opened before the first
build finishes shows no links until then.

## Verification tools

- `tests/run_tests.sh <python-with-esbonio> <scratch-dir>` — builds a fixture
  project through the esbonio agent machinery and asserts recorded locations
  and link resolution (22 checks).
- `tests/probe_project.sh <python> <srcdir> <scratch-dir> [name ...]` — builds
  a real project and reports `std:label` / `std:term` location coverage plus
  optional name resolutions.
- `tests/debug_document_link.sh <python> <esbonio.db> <file.rst>...` — replays
  the documentLink scan for any file against a real esbonio database,
  surfacing exceptions the server would swallow.

## License

Apache-2.0. The role-scanning / link-range arithmetic and the shape of the
objects-database queries are adapted from
[esbonio](https://github.com/swyddfa/esbonio) (MIT License, Copyright (c) 2021
Alex Carney) — see the `esbonio_zed_links` module docstring.
