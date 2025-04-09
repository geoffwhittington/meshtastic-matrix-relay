import logging
import os
from logging.handlers import RotatingFileHandler

from config import relay_config, get_log_dir
from cli import parse_arguments


def get_logger(name):
    logger = logging.getLogger(name=name)
    log_level = getattr(logging, relay_config["logging"]["level"].upper())
    logger.setLevel(log_level)
    logger.propagate = False

    # Add stream handler (console logging)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S %z",
        )
    )
    logger.addHandler(stream_handler)

    # Check command line arguments for log file path
    args = parse_arguments()

    # Check if file logging is enabled
    if relay_config["logging"].get("log_to_file", False) or args.logfile:
        # Priority: 1. Command line arg, 2. Config file, 3. Default location
        if args.logfile:
            log_file = args.logfile
        else:
            # Default to standard log directory if no filename is provided in config
            default_log_file = os.path.join(get_log_dir(), "mmrelay.log")
            log_file = relay_config["logging"].get("filename", default_log_file)

        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:  # Ensure non-empty directory paths exist
            os.makedirs(log_dir, exist_ok=True)

        # Log which file we're using (only for the first logger)
        if name == "M<>M Relay":
            print(f"Logging to: {log_file}")

        # Set up size-based log rotation
        max_bytes = relay_config["logging"].get(
            "max_log_size", 10 * 1024 * 1024
        )  # Default 10 MB
        backup_count = relay_config["logging"].get(
            "backup_count", 1
        )  # Default to 1 backup
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )

        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S %z",
            )
        )
        logger.addHandler(file_handler)

    return logger
