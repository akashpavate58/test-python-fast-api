class AppError(Exception):
    """Base application exception."""

    error_code: str = "application_error"
    status_code: int = 400

    def __init__(
        self,
        message: str = "Application error.",
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message

        if error_code is not None:
            self.error_code = error_code

        if status_code is not None:
            self.status_code = status_code

    def __str__(self) -> str:
        return self.message
