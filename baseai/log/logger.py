from __future__ import annotations
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

# -------------------------------------------------------------------
# Base Paths & Config
# -------------------------------------------------------------------

LOG_ROOT = Path("baseai/logs")
LOG_ROOT.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = (
    "%(asctime)s,%(msecs)03d - [%(levelname)s] " "- (BaseAI | %(name)s:%(lineno)d) - %(message)s"
)
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# -------------------------------------------------------------------
# Internal Builders
# -------------------------------------------------------------------


def _build_file_handler(name: str) -> RotatingFileHandler:
    """Create rotating file handler for a given sub-system."""
    log_file = LOG_ROOT / f"{name}.log"
    handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def _build_console_handler() -> logging.StreamHandler:
    """Colorized console handler."""

    class ColorFormatter(logging.Formatter):
        COLORS = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[41m",  # Red background
        }
        RESET = "\033[0m"

        def format(self, record: logging.LogRecord) -> str:
            color = self.COLORS.get(record.levelname, self.RESET)
            message = super().format(record)
            return f"{color}{message}{self.RESET}"

    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(LOG_FORMAT, DATE_FORMAT))
    return handler


def _build_logger(name: str) -> logging.Logger:
    """Build logger with both console and file handlers."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_build_console_handler())
        logger.addHandler(_build_file_handler(name))
        logger.propagate = False
    return logger


# -------------------------------------------------------------------
# Subsystem Loggers
# -------------------------------------------------------------------

core_logger = _build_logger("core")
bridge_logger = _build_logger("bridge")
audit_logger = _build_logger("audit")

__all__ = ["core_logger", "bridge_logger", "audit_logger"]
