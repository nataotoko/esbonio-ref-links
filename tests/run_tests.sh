#!/usr/bin/env bash
# usage: run_tests.sh <python> <workdir>
#
# <python> must have esbonio and sphinx installed (e.g. a project venv that
# runs esbonio). stderr carries progress/debug output, stdout the summary.
set -euxo pipefail

PYTHON="${1:?usage: run_tests.sh <python> <workdir>}"
WORKDIR="${2:?usage: run_tests.sh <python> <workdir>}"
HERE="$(cd "$(dirname "$0")" && pwd)"

exec "$PYTHON" "$HERE/run_tests.py" --workdir "$WORKDIR"
