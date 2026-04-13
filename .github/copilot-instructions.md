This repository is a Python FastAPI backend service with a `src/app` package layout. Copilot should treat the application as a backend API service, not a generic script.

- Preserve the project architecture. Do not bypass `app.main.create_app`, do not add ad hoc entrypoints, and do not introduce patterns that diverge from the current router/service/integration/db layering.
- New endpoints must follow the existing `src/app/api/v1/router.py` modular router structure, use typed Pydantic response models, and include or update tests in `tests/`.
- All application code must use complete type hints unless there is a strong technical reason not to.
- Prefer explicit, maintainable code over clever abstractions, magic, or speculative utilities.
- Avoid adding dependencies unless a new package is explicitly necessary and justified in a code comment or PR description.
- Do not hardcode secrets or environment-specific values in source code.
- Do not add direct database queries or external HTTP calls inside route handlers, controllers, or endpoints. Keep those calls inside designated `db`, `integrations`, or `services` layers.
- Reuse existing names and conventions from current modules, including `AppSettings`, `get_settings`, `ErrorResponse`, `HealthReadyResponse`, `HelloResponse`, and `app.main` lifecycle patterns.
- Read existing files before generating new code patterns. Prefer modifying existing modules over creating unnecessary new ones.
- Avoid duplicate utility functions, dead code, placeholder implementations, and speculative abstractions that are not required to solve the current task.
- Suggest code that is compatible with this repository's quality expectations: Ruff, mypy, and pytest.
- Keep route handlers thin and business logic out of API controllers.
- Centralize config access through `app.core.config.get_settings()` and keep middleware and exception handling centralized in `src/app/main.py`.
- When working in `tests/`, use the existing pytest-based style and verify actual API behavior instead of implementation details.

Always make the change fit this project’s established FastAPI backend structure.