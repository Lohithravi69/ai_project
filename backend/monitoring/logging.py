import logging
import os
import sys

from loguru import logger

from backend.config import get_settings


def configure_logging() -> None:
    """Configure application-wide logging once at startup."""

    settings = get_settings()
    os.makedirs("logs", exist_ok=True)
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO" if settings.app_env == "local" else "WARNING",
        backtrace=True,
        diagnose=False,
        serialize=settings.app_env != "local",
        enqueue=True,
    )
    logger.add(
        "logs/backend.log",
        level="INFO",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        backtrace=True,
        diagnose=False,
        serialize=True,
        enqueue=True,
    )
    logging.basicConfig(handlers=[logging.StreamHandler(sys.stdout)], level=logging.INFO, force=True)
