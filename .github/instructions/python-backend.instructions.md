Applies to: `src/app/**`

- Use lowercase snake_case for module and package names. Use PascalCase for classes and snake_case for functions and dependencies.
- Keep route handlers in `src/app/api/v1/endpoints/` thin. They should orchestrate dependencies and return typed response models.
- Do not put business logic in route handlers. Business logic belongs in `src/app/services`, `src/app/integrations`, or `src/app/db` placeholder modules.
- Use FastAPI `APIRouter` for route grouping and include routers through `src/app/api/v1/router.py`.
- Use Pydantic models for request and response contracts. Declare `response_model` on route decorators whenever a response contract is returned.
- Centralize configuration in `src/app/core/config.py` and access it through `get_settings()` and dependency injection.
- Use dependency injection with `Depends()` for services, settings, and shared resources. Keep handlers focused on request validation, dependencies, and response shape.
- Keep middleware and exception handling centralized in `src/app/main.py`. Do not add ad hoc middleware in endpoint modules.
- Use `AppError`, `HTTPException`, or centralized exception handling patterns for error propagation; do not swallow exceptions in route handlers.
- Use structured logging in service and integration layers, but avoid logging directly from route functions except for request-scoped audit points if absolutely necessary.
- Follow existing folder boundaries: `api` for routes, `services` for business behavior, `integrations` for external API integration, `db` for persistence placeholders, `models` for schema definitions, `core` for config/exceptions/logging.
- Prefer readability and straightforward control flow over framework tricks, decorators, or metaprogramming.
- Do not bypass the app factory or project structure when adding new application behavior.
- Keep response contracts and runtime behavior explicit, typed, and easy to reason about.