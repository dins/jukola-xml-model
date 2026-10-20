#!/usr/bin/env bash
set -euf -o pipefail

# time ./clear-all-notebook-cells.sh

# Clear all .ipynb notebooks (outputs + metadata) in parallel.
# rg skips hidden dirs and respects .gitignore, so archive/ is not cleared.
# Parallelism defaults to 4; override with PARALLELISM. Any failure aborts the script.

PARALLELISM="${PARALLELISM:-4}"

function clear_notebook_worker() {
  local file="$1"
  echo "$(date -u +"%F %T")" "Clearing ${file}"
  uv run jupyter nbconvert --ClearOutputPreprocessor.enabled=True --ClearMetadataPreprocessor.enabled=True --inplace "${file}"
}

export -f clear_notebook_worker

trap 'echo "ERROR: notebook clearing failed (see errors above)" >&2' ERR

# shellcheck disable=SC2016  # $1 expands in the inner bash, not here
rg --files -g '*.ipynb' . | xargs -n 1 -P "${PARALLELISM}" bash -c 'clear_notebook_worker "$1"' _
