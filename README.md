# test-python-fast-api

A production-oriented FastAPI service skeleton using a `src` package layout.

## Local setup

Create and activate a virtual environment from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .[dev]
```

## Run

### Local development

Start the application locally with Uvicorn and auto-reload for developer productivity:

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> This is the preferred local workflow for fast feedback while editing the code.

### Production-ready deployment guidance

For production, use a worker-based server process manager such as Gunicorn with Uvicorn workers.
A common deployment pattern is:

```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --log-level info
```

Do not use `--reload` in production. Tune the worker count for your environment; a common starting formula is `(2 x $CPU_CORES) + 1`, but the final value depends on deployment size, latency, concurrency, and memory limits.

If you do not have Gunicorn installed in your production environment, install it separately:

```bash
python -m pip install gunicorn
```

## Quality commands

1. Install dependencies

```bash
python -m pip install -e .[dev]
```

2. Run Ruff

```bash
ruff check .
```

3. Run mypy

```bash
mypy src
```

4. Run pytest

```bash
pytest
```

## Additional checks

Run formatting verification with Black:

```bash
black --check src tests
```

Run linting and import ordering checks with Ruff:

```bash
ruff check .
```

Run static type checking on application code in `src/app`:

```bash
mypy src
```

Run the test suite:

```bash
pytest
```

## Coding Standards and Copilot Instructions

This repository stores human-readable standards in `docs/engineering-standards.md` and GitHub Copilot guidance in `.github/copilot-instructions.md`.

Path-specific Copilot guidance is kept in `.github/instructions/python-backend.instructions.md` for backend source and `.github/instructions/tests.instructions.md` for tests.

Keep these files up to date when repository conventions or architecture patterns change.
