#!/usr/bin/env bash
# usage: debug_document_link.sh <python> <dbpath> <rstfile> [rstfile ...]
set -euxo pipefail

PYTHON="${1:?usage: debug_document_link.sh <python> <dbpath> <rstfile>...}"
shift
HERE="$(cd "$(dirname "$0")" && pwd)"

exec "$PYTHON" "$HERE/debug_document_link.py" "$@"
