#!/usr/bin/env bash
set -eu -o pipefail

# time ./clear-all-notebook-cells.sh

for file in *.ipynb; do
  echo $(date -u +"%F %T") "Clearing ${file}"
  pipenv run jupyter nbconvert --ClearOutputPreprocessor.enabled=True --ClearMetadataPreprocessor.enabled=True --inplace "${file}"
done
