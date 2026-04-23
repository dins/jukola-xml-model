# uv Usage Guide

This document describes how to use `uv` in this project for Python package management, script execution, and development workflows.

## Table of Contents
- [Virtual Environment Management](#virtual-environment-management)
- [Running Scripts](#running-scripts)
- [Package Management](#package-management)
- [Development Workflows](#development-workflows)
- [Common Patterns](#common-patterns)

---

## Virtual Environment Management

### Creating and Syncing the Virtual Environment

The project uses a `pyproject.toml` file to declare dependencies. Sync the virtual environment with:

```bash
uv sync
```

This reads `pyproject.toml` and `uv.lock` to install all dependencies into the project's virtual environment.

### Updating Dependencies

After modifying `pyproject.toml`, update the lock file and install:

```bash
uv sync
```

To add a new dependency:

```bash
uv add package-name
```

To add a dependency with version constraints:

```bash
uv add "package-name>=1.2.0,<2"
```

To remove a dependency:

```bash
uv remove package-name
```

To update all dependencies to their latest versions:

```bash
uv lock --upgrade
```

To update a specific package:

```bash
uv lock --upgrade package-name
```

### Lock File

The `uv.lock` file pins exact versions of all dependencies and their transitive dependencies. Always commit this file to version control to ensure reproducible builds.

### Python Version Management

Pin a Python version for the project:

```bash
uv python pin 3.13
```

Unpin to use the system Python:

```bash
uv python pin --unset
```

List available Python versions:

```bash
uv python list
```

Install a specific Python version:

```bash
uv python install 3.13
uv python install 3.14
```

---

## Running Scripts

### Using `uv run`

The `uv run` command executes a command within the project's virtual environment. This is the primary way to run Python scripts in this project.

#### Basic Pattern

```bash
uv run python script.py [arguments]
```

#### Examples from This Project

**Running a data processing script:**

```bash
uv run python result_xml_to_csv.py 2023 ve
```

**Running with timing:**

```bash
time uv run python result_xml_to_csv.py 2023 ve
```

**Running with environment variables:**

```bash
RACE_TYPE=ve FORECAST_YEAR=2025 uv run python fetch_team_countries.py 2025
```

**Running in a loop:**

```bash
for year in $(seq 2009 2019); do
    echo "YEAR $year"
    time uv run python fetch_team_countries.py ${year}
done
```

**Running Jupyter notebooks:**

```bash
uv run jupyter notebook
```

**Running a Python one-liner:**

```bash
uv run python -c "import pandas; print(pandas.__version__)"
```

### Why `uv run`?

- Automatically activates the correct virtual environment
- No need to manually activate/deactivate virtual environments
- Ensures all required packages are available
- Fast execution via uv's optimized resolver

---

## Package Management

### Managing Dependencies

Dependencies are declared in `pyproject.toml`:

```toml
[project]
name = "jukola-xml-model"
version = "0.1.0"
requires-python = ">=3.13,<3.15"
dependencies = [
    "scikit-learn>=1.2.0,<2",
    "pandas>=2.3.3,<3",
    "ruff>=0.15.11",
    # ... more dependencies
]
```

After editing `pyproject.toml`, run:

```bash
uv sync
```

### Adding Dependencies

To add a new dependency:

```bash
uv add package-name
```

To add a development-only dependency:

```bash
uv add --dev package-name
```

To add an optional dependency group:

```bash
uv add --optional dev package-name
```

### Removing Dependencies

To remove a dependency:

```bash
uv remove package-name
```

---

## Development Workflows

### Code Linting with Ruff

```bash
# Check code
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .

# Check a single file
uv run ruff check script.py

# List violations with line numbers
uv run ruff check . --output-format=full
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest tests/test_group_names.py

# Run with coverage
uv run pytest --cov=.
```

### Using Jupyter Notebooks

```bash
# Start Jupyter notebook server
uv run jupyter notebook

# Start Jupyter lab
uv run jupyter lab
```

**Important:** For time measurement in notebooks, install the execute time extension:

```bash
uv run jupyter contrib nbextension install --user
uv run jupyter nbextension enable execute_time/ExecuteTime
```

---

## Common Patterns

### Running Shell Scripts with uv

For shell scripts that invoke Python, wrap commands with `uv run`:

```bash
#!/bin/bash
# process-one-race.sh

RACE_TYPE="${1:-ve}"
YEAR="${2:-2025}"

time uv run python result_xml_to_csv.py "$YEAR" "$RACE_TYPE"
time uv run python count_names.py
```

### Parallel Execution with uv

```bash
# Run multiple scripts in parallel (background)
time uv run python script1.py &
time uv run python script2.py &
wait
```

### Batch Processing Loop

```bash
# Process multiple years
for year in $(seq 2019 2025); do
    echo "Processing year: $year"
    time uv run python result_xml_to_csv.py "$year" "ve"
done
```

### Environment Variable Usage

```bash
# Set environment variables before uv run
RACE_TYPE=ju FORECAST_YEAR=2025 uv run python fetch_team_countries.py 2025

# Or set variables in the shell first
export RACE_TYPE=ve
export FORECAST_YEAR=2025
uv run python fetch_online_team_countries.py
```

### Quick Python Execution

```bash
# Run inline Python code
uv run python -c "print('Hello from uv!')"

# Run with imports
uv run python -c "import pandas as pd; print(pd.__version__)"
```

### Debugging with uv

```bash
# Run a script with verbose output
uv run --verbose python script.py

# Check which Python is being used
uv run python -c "import sys; print(sys.executable)"

# List installed packages via Python
uv run python -c "import importlib.metadata; [(d.metadata['Name'], d.metadata['Version']) for d in importlib.metadata.distributions()]"
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Sync dependencies | `uv sync` |
| Run Python script | `uv run python script.py` |
| Run command in env | `uv run command args` |
| Run Jupyter | `uv run jupyter notebook` |
| Lint with ruff | `uv run ruff check .` |
| Format with ruff | `uv run ruff format .` |
| Add dependency | `uv add package-name` |
| Add dev dependency | `uv add --dev package-name` |
| Remove dependency | `uv remove package-name` |
| Lock file update | `uv lock --upgrade` |
| Pin Python version | `uv python pin 3.13` |
| List Python versions | `uv python list` |
| Install Python version | `uv python install 3.13` |

---

## Notes

- The `uv.lock` file should always be committed to version control
- Virtual environment is automatically created in `.venv/` within the project directory
- No need to run `source .venv/bin/activate` — `uv run` handles activation automatically
- All commands in this project should use `uv run` to ensure correct package availability
- Use `uv add` / `uv remove` for dependency management (not `uv pip install`)