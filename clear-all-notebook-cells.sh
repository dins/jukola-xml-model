#!/usr/bin/env bash
set -euf -o pipefail

# Clear outputs + metadata from all notebooks in . and exploration/.
uv run jupyter nbconvert --ClearOutputPreprocessor.enabled=True --ClearMetadataPreprocessor.enabled=True --inplace ./*.ipynb exploration/*.ipynb
