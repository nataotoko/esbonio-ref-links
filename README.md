# esbonio-ref-links workspace

A [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/)
bundling two independently installable packages, developed together under one
lockfile and virtual environment:

- **`packages/esbonio-ref-links/`** — line-precise document links for reST
  references in [esbonio](https://github.com/swyddfa/esbonio) (an esbonio
  server module plus a Sphinx extension).
- **`packages/sphinx-ref-extras/`** — standalone Sphinx reference/label
  extensions: a nearest-in-toctree `sref` role, delimiter-scoped section
  prefixes, and a `word_` term/label fallback.

The two packages share no code; the workspace exists only to develop and version
them side by side. Each has its own `README.md` and `pyproject.toml` under
`packages/<name>/`.

## Development

```
uv sync                               # create .venv, editable-install both members + their deps
uv sync --package sphinx-ref-extras   # operate on a single member
```

## Build / publish a member

```
uv build --package sphinx-ref-extras
uv build --package esbonio-ref-links
```

Each member is a separate distribution; build and `uv publish` them individually.
