#!/usr/bin/env bash
set -eu -o pipefail

# time ./clear-all-notebook-cells.sh

# Find all .ipynb files, excluding any hidden directories like .ipynb_checkpoints/ or .venv/
find . -type f -name "*.ipynb" -not -path "*/\.*" | while read -r file; do
  echo $(date -u +"%F %T") "Clearing ${file}"
  uv run jupyter nbconvert --ClearOutputPreprocessor.enabled=True --ClearMetadataPreprocessor.enabled=True --inplace "${file}"
done
