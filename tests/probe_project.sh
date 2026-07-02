#!/usr/bin/env bash
# usage: probe_project.sh <python> <srcdir> <workdir> [name ...]
#
# <python> must have esbonio, sphinx, the project's build deps and
# esbonio-zed-links installed. stderr = build output, stdout = report.
set -euxo pipefail

PYTHON="${1:?usage: probe_project.sh <python> <srcdir> <workdir> [name ...]}"
SRCDIR="${2:?usage: probe_project.sh <python> <srcdir> <workdir> [name ...]}"
WORKDIR="${3:?usage: probe_project.sh <python> <srcdir> <workdir> [name ...]}"
shift 3
HERE="$(cd "$(dirname "$0")" && pwd)"

exec "$PYTHON" "$HERE/probe_project.py" --srcdir "$SRCDIR" --workdir "$WORKDIR" "$@"
