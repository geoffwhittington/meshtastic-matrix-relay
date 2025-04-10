import logging
import os
from logging.handlers import RotatingFileHandler

from mmrelay.cli import parse_arguments
from mmrelay.config import get_log_dir, relay_config


def get_logger(name):
    logger = logging.getLogger(name=name)

    # Default to INFO level if config is not available
    log_level = logging.INFO

    # Try to get log level from config
    if (
        relay_config
        and "logging" in relay_config
        and "level" in relay_config["logging"]
    ):
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
    if relay_config.get("logging", {}).get("log_to_file", False) or args.logfile:
        # Priority: 1. Command line arg, 2. Config file, 3. Default location (~/.mmrelay/logs)
        if args.logfile:
            log_file = args.logfile
        else:
            config_log_file = relay_config.get("logging", {}).get("filename")

            if config_log_file:
                # Use the log file specified in config
                log_file = config_log_file
            else:
                # Default to standard log directory
                log_file = os.path.join(get_log_dir(), "mmrelay.log")

        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:  # Ensure non-empty directory paths exist
            os.makedirs(log_dir, exist_ok=True)

        # Log which file we're using (only for the first logger)
        if name == "M<>M Relay":
            # Create a basic logger to log the log file path
            # This is needed because we can't use the logger we're creating to log its own creation
            basic_logger = logging.getLogger("LogSetup")
            basic_logger.setLevel(logging.INFO)
            basic_handler = logging.StreamHandler()
            basic_handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S %z",
                )
            )
            basic_logger.addHandler(basic_handler)
            basic_logger.info(f"Writing logs to: {log_file}")

        # Create a file handler for logging
        try:
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
        except Exception as e:
            print(f"Error creating log file at {log_file}: {e}")
            return logger  # Return logger without file handler

        file_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s:%(name)s:%(message)s",
                datefmt="%Y-%m-%d %H:%M:%S %z",
            )
        )
        logger.addHandler(file_handler)

    return logger
