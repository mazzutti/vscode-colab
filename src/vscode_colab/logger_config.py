import sys

from loguru import logger

# Configure Loguru
# Handler 1: Console output (INFO and above)
logger.remove()  # Remove default handlers
logger.add(
    sys.stderr,
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} - {level} - [{function}] {message}",
)

# Handler 2: File output (DEBUG and above, appending)
# This handler saves all messages from DEBUG level upwards to a file.
# It will append to the file if it already exists.
logger.add(
    "script_activity.log",  # Name of the log file
    level="DEBUG",  # Log all messages from DEBUG level upwards
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{module}:{function}:{line} - {message}",  # A more detailed format for file logs
    mode="a",  # Explicitly set append mode (though it's default for files)
    encoding="utf-8",  # Specify encoding for the log file
    # Optional: Add rotation or retention policies if the log file might grow too large
    # rotation="10 MB",    # e.g., rotate when file reaches 10 MB
    # retention="7 days",  # e.g., keep logs for 7 days
)

# Export the configured logger
log = logger
