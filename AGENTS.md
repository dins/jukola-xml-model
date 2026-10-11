# Agent notes

## Permissions

You are allowed to do read-only operations ONLY and edit files in this repo.

Allowed shell commands are listed in `.vibe/config.toml`. Strongly prefer commands explicitly listed there. 

Try to avoid interrupting your workflow with need to ask permissions. STICK TO ALLOWED COMMANDS or rarely suggest if some command would be safe to add.

To view part of a file, use the read tool’s offset/limit; don’t use sed or awk.

## Static checks and tests

Always run this single command for static checks and tests before considering a task done:

```sh
./run-all-local-checks.sh
```

- `ruff check` lints all top-level `.py` files, notebooks and the `tests/` directory.
- `ty check` runs type checking on the same set.
- `PYTHONPATH=.` is required so `pytest` can import the project's top-level modules from `tests/`.

## Don'ts

- Do NOT run `git checkout`, `git restore`, or any other destructive git command to "undo" your own changes. Ask the user how to proceed instead.
- Do NOT run `uv run ruff format` across the whole project unless explicitly asked.
- Do NOT modify shared fixture files in `tests/testdata/default-set/` for a new test. Create a sibling subfolder under `tests/testdata/` and use `@pytest.mark.testdata("<subdir>")` instead.
- Do NOT use `cd` in shell commands — use `pwd` to verify the current working directory when uncertain; relative paths resolve from the current dir, and absolute paths work without `cd`.
- Do NOT suggest potentially harmfull arbitrary code with `sed`,`awk`,`python -C *`,`uv run python -C *` or any other. Instead, use safe read-only tools if they do roughly the same thing.
- Do NOT improvise alternative ways to do what your already allowed comamnds could achieve. Reviewing those permission requests just burdens user and wastes time. 
