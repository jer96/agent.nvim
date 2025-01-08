import logging
import os
from datetime import datetime


def setup_logger():
    # Create logs directory if it doesn't exist
    log_dir = os.path.expanduser("~/nvim-plugins/logs")
    os.makedirs(log_dir, exist_ok=True)

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create file handler
    log_file = os.path.join(
        log_dir,
        f'nvim_plugin_{
            datetime.now().strftime("%Y%m%d")}.log',
    )
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(file_handler)

    return logger
