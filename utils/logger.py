import logging
import os
import sys

def setup_logger(name="QuantSystem", log_file="logs/quant_system.log", level=logging.INFO):
    """
    Sets up a logger with both file and console handlers.
    """
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if not logger.handlers:
        # File handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger

# Default logger instance
logger = setup_logger()
