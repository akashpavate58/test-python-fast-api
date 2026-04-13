Applies to: `tests/**`

- Use the existing pytest-based approach used in this repository.
- For API tests, use the project-standard test client pattern for FastAPI, such as `TestClient` for synchronous tests or `httpx.AsyncClient` for async tests.
- Keep tests deterministic, isolated, and repeatable. Do not call real external services or databases from tests.
- Reset any environment changes or settings patches between tests.
- Test behavior, not implementation details. Prefer assertions on requests and responses over internal function calls.
- Each test name should clearly describe the scenario and the expected outcome.
- Assert HTTP status codes explicitly.
- Assert response body shape and key fields, not incidental formatting.
- Assert required headers when relevant, such as `X-Request-ID` or content-type headers.
- Avoid brittle assertions on exact text formatting, stack traces, or internal logs.
- When adding coverage for a bug fix, include at least one regression test that captures the failing behavior.

Use tests to validate the public API contract and integration points, not private implementation details.