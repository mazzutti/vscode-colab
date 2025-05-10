import logging
import os
import sys

from loguru import logger

# --- Default Configuration ---
DEFAULT_CONSOLE_LOG_LEVEL = "INFO"
DEFAULT_CONSOLE_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>"
)

ENABLE_FILE_LOGGING_ENV_VAR = "VSCODE_COLAB_ENABLE_FILE_LOGGING"
DEFAULT_FILE_LOG_PATH = "vscode_colab_activity.log"
DEFAULT_FILE_LOG_LEVEL = "DEBUG"
DEFAULT_FILE_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{name}:{module}:{function}:{line} - {message}"
)

# --- Apply Configuration ---
logger.remove()

console_log_level = os.getenv(
    "VSCODE_COLAB_CONSOLE_LOG_LEVEL", DEFAULT_CONSOLE_LOG_LEVEL
).upper()
logger.add(
    sys.stderr,
    level=console_log_level,
    format=DEFAULT_CONSOLE_LOG_FORMAT,
    colorize=True,
)

if os.getenv(ENABLE_FILE_LOGGING_ENV_VAR, "false").lower() in ["true", "1", "yes"]:
    file_log_path = os.getenv("VSCODE_COLAB_LOG_FILE_PATH", DEFAULT_FILE_LOG_PATH)
    file_log_level = os.getenv(
        "VSCODE_COLAB_FILE_LOG_LEVEL", DEFAULT_FILE_LOG_LEVEL
    ).upper()

    logger.info(f"File logging enabled. Level: {file_log_level}, Path: {file_log_path}")
    try:
        logger.add(
            file_log_path,
            level=file_log_level,
            format=DEFAULT_FILE_LOG_FORMAT,
            mode="a",
            encoding="utf-8",
            rotation="10 MB",
            retention="3 days",
        )
    except Exception as e:
        logger.warning(
            f"Could not configure file logger at '{file_log_path}': {e}. File logging disabled."
        )


class PropagateHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        logging.getLogger(record.name).handle(record)


if (
    "pytest" in sys.modules
    or os.getenv("VSCODE_COLAB_PROPAGATE_LOGS", "false").lower() == "true"
):
    logger.add(PropagateHandler(), format="{message}", level="DEBUG")
    if "pytest" in sys.modules:  # Only log this info if pytest is detected
        logger.debug("Loguru to standard logging propagation enabled for pytest.")


log = logger
