import logging
import os
from logging.handlers import TimedRotatingFileHandler

import structlog

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

handlers: list[logging.Handler] = [logging.StreamHandler()]
log_file = os.getenv("LOG_FILE")
if log_file:
    handlers.append(TimedRotatingFileHandler(log_file, when="midnight", backupCount=7))

logging.basicConfig(format="%(message)s", level=LOG_LEVEL, handlers=handlers)

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
