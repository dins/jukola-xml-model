import logging
import os

LOG_FORMAT = (
    "%(asctime)s - %(name)s [%(threadName)s] %(funcName)s [%(levelname)s] %(message)s"
)


def configure_logging(logger_name: str | None = None) -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        format=LOG_FORMAT,
    )
    return logging.getLogger(logger_name)
