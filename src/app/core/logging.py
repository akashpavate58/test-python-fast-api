import contextvars
import logging

request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def get_request_id() -> str:
    return request_id_ctx_var.get("")


class RequestIDLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def init_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(request_id)s - %(message)s",
    )

    request_id_filter = RequestIDLogFilter()
    root_logger = logging.getLogger()
    root_logger.addFilter(request_id_filter)

    for handler in root_logger.handlers:
        handler.addFilter(request_id_filter)
