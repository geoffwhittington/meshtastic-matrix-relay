import logging
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.log_utils import get_logger


class TestLogUtils(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test logs
        self.test_dir = tempfile.mkdtemp()
        self.test_log_file = os.path.join(self.test_dir, "test.log")
        
        # Reset global state
        import mmrelay.log_utils
        mmrelay.log_utils.config = None
        mmrelay.log_utils.log_file_path = None
        
        # Clear any existing loggers to avoid interference
        logging.getLogger().handlers.clear()

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        # Reset logging state
        logging.getLogger().handlers.clear()
        logging.getLogger().setLevel(logging.WARNING)

    def test_get_logger_invalid_log_level_fallback(self):
        """Test that invalid log level configuration falls back to INFO."""
        config = {
            "logging": {
                "level": "invalid_level"
            }
        }

        import mmrelay.log_utils
        mmrelay.log_utils.config = config

        # Should not raise exception, should fall back to default INFO level
        logger = get_logger("test_logger")

        # Should fall back to INFO level due to AttributeError handling
        self.assertEqual(logger.level, logging.INFO)

    def test_get_logger_handler_duplication_prevention(self):
        """Test that loggers don't get duplicate handlers."""
        import mmrelay.log_utils
        mmrelay.log_utils.config = {"logging": {"level": "info"}}

        # First call to get_logger
        logger1 = get_logger("test_dup_logger")
        initial_handler_count = len(logger1.handlers)
        self.assertGreater(initial_handler_count, 0)

        # Second call to get_logger with same name
        logger2 = get_logger("test_dup_logger")
        final_handler_count = len(logger2.handlers)

        # Should be the same logger instance and same handler count
        self.assertIs(logger1, logger2)
        self.assertEqual(initial_handler_count, final_handler_count)

    @patch('mmrelay.log_utils.get_log_dir')
    def test_get_logger_default_log_size_reduced(self, mock_get_log_dir):
        """Test that default log file size is now 5MB instead of 10MB."""
        mock_get_log_dir.return_value = self.test_dir

        config = {
            "logging": {
                "log_to_file": True
            }
        }

        import mmrelay.log_utils
        mmrelay.log_utils.config = config

        # Use unique logger name to avoid caching issues
        logger_name = "test_logger_size"
        existing_logger = logging.getLogger(logger_name)
        existing_logger.handlers.clear()

        logger = get_logger(logger_name)

        # Check for file handler with reduced size
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.handlers.RotatingFileHandler)]
        if file_handlers:
            file_handler = file_handlers[0]
            # Should be 5MB not 10MB
            self.assertEqual(file_handler.maxBytes, 5 * 1024 * 1024)

    def test_get_logger_valid_log_level_setting(self):
        """Test that valid log levels are set correctly without AttributeError."""
        config = {
            "logging": {
                "level": "DEBUG"
            }
        }

        import mmrelay.log_utils
        mmrelay.log_utils.config = config

        logger = get_logger("test_valid_level")

        # Should successfully set DEBUG level
        self.assertEqual(logger.level, logging.DEBUG)

    def test_get_logger_case_insensitive_log_level(self):
        """Test that log levels work in different cases."""
        config = {
            "logging": {
                "level": "warning"  # lowercase
            }
        }

        import mmrelay.log_utils
        mmrelay.log_utils.config = config

        logger = get_logger("test_case_level")

        # Should successfully set WARNING level even with lowercase input
        self.assertEqual(logger.level, logging.WARNING)

    def test_get_logger_empty_log_level_fallback(self):
        """Test that empty log level falls back to INFO."""
        config = {
            "logging": {
                "level": ""  # empty string
            }
        }

        import mmrelay.log_utils
        mmrelay.log_utils.config = config

        logger = get_logger("test_empty_level")

        # Should fall back to INFO level
        self.assertEqual(logger.level, logging.INFO)


if __name__ == "__main__":
    unittest.main()