#!/usr/bin/env bash
set -euo pipefail

echo "=== ruff check ==="
uv run ruff check *.py *.ipynb tests

echo "=== ty check ==="
uv run ty check *.py tests/

echo "=== pytest ==="
PYTHONPATH=. uv run pytest
