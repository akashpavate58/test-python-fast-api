# Engineering Standards

## Purpose and scope
This document is the authoritative human-readable source for coding standards in this FastAPI backend service. It applies to all contributors and reviewers working in `src/app`, `tests`, and repository documentation.

## Architecture rules
- Preserve the existing package layout: `src/app/main.py`, `src/app/api/v1`, `src/app/services`, `src/app/integrations`, `src/app/db`, `src/app/models`, and `src/app/core`.
- New endpoints must be added under `src/app/api/v1/endpoints` and included through `src/app/api/v1/router.py`.
- Route handlers must be thin. Business logic belongs in the service, integration, or database layer.
- Do not add direct database or external API calls inside route handlers.
- Keep new infrastructure in designated layers: `db` for persistence placeholders, `integrations` for external APIs, `services` for domain behavior.
- Do not bypass `create_app()` or the established lifecycle in `src/app/main.py`.

## Python style rules
- Use lowercase snake_case for modules and functions.
- Use PascalCase for classes and exception types.
- Keep files focused and small. Prefer one primary responsibility per module.
- Prefer explicit, readable code over clever abstractions and magic.
- Avoid dead code, placeholder implementations, and unnecessary helper functions.

## FastAPI conventions
- Use `APIRouter` and route inclusion in `src/app/api/v1/router.py`.
- Declare response contracts with Pydantic models and use `response_model` on route decorators.
- Keep route handlers focused on request handling, dependency wiring, and response shape.
- Centralize middleware and exception handlers in `src/app/main.py`.
- Prefer `Depends()` for service and settings injection.

## Typing rules
- Use complete type hints in application code unless there is a strong technical reason not to.
- Type all public function signatures, route parameters, return values, and dependency providers.
- Use Pydantic models for API contracts and typed settings in `src/app/core/config.py`.
- Keep types explicit and avoid `Any` unless absolutely justified.

## Testing rules
- Use pytest for all project tests.
- Write or update tests for every functional change.
- Bug fixes should include at least one regression test when practical.
- Keep tests deterministic, isolated, and independent of real external services.
- Assert HTTP status codes, response body shape, and required headers where relevant.
- Avoid brittle assertions on incidental formatting or internal implementation details.

## Error handling rules
- Centralize exception handling in `src/app/main.py`.
- Use application-specific errors such as `AppError` or FastAPI exceptions for route-level problems.
- Do not swallow exceptions in route handlers. Allow centralized handlers to convert them into API responses.
- Do not expose raw stack traces or internal errors to clients.

## Logging rules
- Initialize logging centrally in `src/app/main.py`.
- Use structured log messages in service and integration layers.
- Avoid ad hoc logging in route handlers unless needed for request-scoped audit or tracing.
- Preserve request IDs across the request lifecycle and return them in responses when available.

## Dependency management rules
- Avoid adding dependencies casually. Add new packages only when clearly necessary and justified in the PR.
- Prefer standard library and existing project utilities.
- Keep external integration code in `src/app/integrations` and persistence placeholders in `src/app/db`.
- Do not hardcode secrets or environment-specific values in source code.

## Pull request expectations
- Keep PRs focused in scope.
- Every feature change requires tests, unless explicitly exempted and documented.
- Every bug fix should include a regression test where practical.
- Follow existing module placement and naming conventions.
- Run quality checks before marking work complete: `ruff check .`, `mypy src`, and `pytest`.
- Update this document and the Copilot instruction files when conventions or architecture change.

## Rules for using GitHub Copilot in this repository
- Repository-wide instructions live in `.github/copilot-instructions.md`.
- Path-specific instructions live in `.github/instructions/python-backend.instructions.md` and `.github/instructions/tests.instructions.md`.
- Copilot should read existing files before generating code and reuse current naming and architecture patterns.
- Keep Copilot instruction files current when repository conventions evolve.
- Treat Copilot guidance as supplemental to the human-reviewed standards in this document.