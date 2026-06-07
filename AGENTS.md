# Agent notes

## Static checks and tests

Always run this single command for static checks and tests before considering a task done:

```sh
uv run ruff check *.py *.ipynb tests && uv run ty check *.py tests/ && time PYTHONPATH=. uv run pytest
```

- `ruff check` lints all top-level `.py` files, notebooks and the `tests/` directory.
- `ty check` runs type checking on the same set.
- `PYTHONPATH=.` is required so `pytest` can import the project's top-level modules from `tests/`.

## Don'ts

- Do NOT run `git checkout`, `git restore`, or any other destructive git command to "undo" your own changes. Ask the user how to proceed instead.
- Do NOT run `uv run ruff format` across the whole project unless explicitly asked.
- Do NOT modify shared fixture files in `tests/testdata/default-set/` for a new test. Create a sibling subfolder under `tests/testdata/` and use `@pytest.mark.testdata("<subdir>")` instead.
