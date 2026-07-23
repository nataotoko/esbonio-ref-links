#!/usr/bin/env bash
# usage: setup_venv.sh
#
# Creates/updates the uv workspace root's .venv (../../../pyproject.toml) with
# the `test` dependency group (esbonio + sphinx) -- esbonio-ref-links itself
# ships with no dependencies (see packages/esbonio-ref-links/pyproject.toml),
# so run_tests.py needs a python where esbonio is importable to build the
# fixture project and exercise document_links / object_locations against a
# real esbonio.db.
#
# stdout: the resulting python executable path (feed straight into
#         run_tests.sh <python> <workdir>).
# stderr: uv's own progress output.
set -euxo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"

uv --project "$ROOT" sync --group test 1>&2

if [[ -x "$ROOT/.venv/Scripts/python.exe" ]]; then
    echo "$ROOT/.venv/Scripts/python.exe"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
    echo "$ROOT/.venv/bin/python"
else
    echo "setup_venv.sh: no python executable found under $ROOT/.venv" >&2
    exit 1
fi
