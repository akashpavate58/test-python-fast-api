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

Start the application locally with Uvicorn:

```bash
uvicorn app.main:app --reload
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
