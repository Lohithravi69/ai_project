from loguru import logger

from backend.config import get_settings


def configure_logging() -> None:
    """Configure application-wide logging once at startup."""

    settings = get_settings()
    logger.remove()
    logger.add(
        sink=lambda message: print(message, end=""),
        level="INFO" if settings.app_env == "local" else "WARNING",
        backtrace=True,
        diagnose=True,
    )
