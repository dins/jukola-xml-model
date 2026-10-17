#!/usr/bin/env bash
set -eu -o pipefail

# time ./clear-all-notebook-cells.sh

# Find all .ipynb files, excluding any hidden directories like .ipynb_checkpoints/ or .venv/.
# rg is far faster than find here: it skips hidden dirs by default and respects .gitignore.
# `archive` is passed explicitly because it is gitignored but still holds notebooks we want to clear.
rg --files -g '*.ipynb' . archive | while read -r file; do
  echo $(date -u +"%F %T") "Clearing ${file}"
  uv run jupyter nbconvert --ClearOutputPreprocessor.enabled=True --ClearMetadataPreprocessor.enabled=True --inplace "${file}"
done
