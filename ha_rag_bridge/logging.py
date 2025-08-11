import logging
import os
from logging.handlers import TimedRotatingFileHandler

import structlog

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
HA_RAG_LOG_LEVEL = os.getenv("HA_RAG_LOG_LEVEL", "INFO").upper()

handlers: list[logging.Handler] = [logging.StreamHandler()]
log_file = os.getenv("LOG_FILE")
if log_file:
    handlers.append(TimedRotatingFileHandler(log_file, when="midnight", backupCount=7))

class _TokenFilter(logging.Filter):
    TOKEN_ATTRIBUTES = ["admin_token", "api_token", "auth_token"]

    def filter(self, record: logging.LogRecord) -> bool:
        for attr in self.TOKEN_ATTRIBUTES:
            if getattr(record, attr, None):
                setattr(record, attr, "\u2022\u2022\u2022\u2022\u2022")
        return True

for h in handlers:
    h.addFilter(_TokenFilter())

logging.basicConfig(format="%(message)s", level=LOG_LEVEL, handlers=handlers)

# Suppress verbose HTTP request logging from httpx and similar libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# Set specific log levels for HA-RAG components based on environment
if HA_RAG_LOG_LEVEL == "SUMMARY":
    # Summary mode: only show high-level operations and errors
    logging.getLogger("ha-rag-bridge").setLevel(logging.INFO)
    logging.getLogger("app").setLevel(logging.INFO)
elif HA_RAG_LOG_LEVEL == "TRACKING":
    # Tracking mode: show entity tracking but suppress verbose details
    logging.getLogger("ha-rag-bridge").setLevel(logging.INFO)
    logging.getLogger("app").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.ERROR)  # Suppress all HTTP logs except errors

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.contextvars.merge_contextvars,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)


def get_logger(name: str = "ha-rag-bridge"):
    return structlog.get_logger(name)
