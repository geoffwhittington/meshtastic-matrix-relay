#!/usr/bin/env python3
"""
Test suite for CLI module edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- Invalid argument combinations
- File system permission errors
- Missing dependencies and import failures
- Windows-specific argument handling
- Configuration validation edge cases
- Service installation failures
- Sample config generation edge cases
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, mock_open, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.cli import (
    check_config,
    generate_sample_config,
    handle_cli_commands,
    main,
    parse_arguments,
)


class TestCLIEdgeCases(unittest.TestCase):
    """Test cases for CLI module edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Store original sys.argv to restore later
        self.original_argv = sys.argv.copy()

    def tearDown(self):
        """Clean up after each test method."""
        # Restore original sys.argv
        sys.argv = self.original_argv

    def test_parse_arguments_windows_positional_config(self):
        """Test Windows-specific positional config argument handling."""
        with patch("sys.platform", "win32"):
            with patch("sys.argv", ["mmrelay", "config.yaml"]):
                with patch("builtins.print") as mock_print:
                    args = parse_arguments()
                    self.assertEqual(args.config, "config.yaml")
                    # Should print deprecation warning
                    mock_print.assert_called()

    def test_parse_arguments_windows_both_positional_and_flag(self):
        """Test Windows handling when both positional and --config are provided."""
        with patch("sys.platform", "win32"):
            with patch(
                "sys.argv",
                ["mmrelay", "--config", "flag_config.yaml", "pos_config.yaml"],
            ):
                args = parse_arguments()
                # Flag should take precedence
                self.assertEqual(args.config, "flag_config.yaml")

    def test_parse_arguments_invalid_log_level(self):
        """Test argument parsing with invalid log level."""
        with patch("sys.argv", ["mmrelay", "--log-level", "invalid"]):
            with self.assertRaises(SystemExit):
                parse_arguments()

    def test_parse_arguments_pytest_environment(self):
        """Test that unknown arguments are ignored in pytest environment."""
        with patch("sys.argv", ["mmrelay", "--unknown-arg", "pytest"]):
            with patch("builtins.print") as mock_print:
                parse_arguments()
                # Should not print warning in test environment
                mock_print.assert_not_called()

    def test_check_config_file_permission_error(self):
        """Test check_config behavior with file permission errors."""
        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/test/config.yaml"]
            with patch("os.path.isfile", return_value=True):
                with patch(
                    "builtins.open", side_effect=PermissionError("Permission denied")
                ):
                    with patch("builtins.print") as mock_print:
                        result = check_config()
                        self.assertFalse(result)
                        mock_print.assert_called()

    def test_check_config_yaml_syntax_error(self):
        """Test check_config behavior with YAML syntax errors."""
        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/test/config.yaml"]
            with patch("os.path.isfile", return_value=True):
                with patch("builtins.open", mock_open(read_data="invalid: yaml: [")):
                    with patch("builtins.print") as mock_print:
                        result = check_config()
                        self.assertFalse(result)
                        # Should print YAML error
                        mock_print.assert_called()

    def test_check_config_empty_file(self):
        """Test check_config behavior with empty configuration file."""
        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/test/config.yaml"]
            with patch("os.path.isfile", return_value=True):
                with patch("builtins.open", mock_open(read_data="")):
                    with patch("yaml.load", return_value=None):
                        with patch("builtins.print") as mock_print:
                            result = check_config()
                            self.assertFalse(result)
                            mock_print.assert_called()

    def test_check_config_missing_required_sections(self):
        """Test check_config with missing required configuration sections."""
        invalid_configs = [
            {},  # Empty config
            {"matrix": {}},  # Missing matrix fields
            {
                "matrix": {"homeserver": "test"},
                "meshtastic": {},
            },  # Missing matrix_rooms
            {
                "matrix": {
                    "homeserver": "test",
                    "access_token": "test",
                    "bot_user_id": "test",
                }
            },  # Missing meshtastic
        ]

        for config in invalid_configs:
            with self.subTest(config=config):
                with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
                    mock_get_paths.return_value = ["/test/config.yaml"]
                    with patch("os.path.isfile", return_value=True):
                        with patch("builtins.open", mock_open()):
                            with patch("yaml.load", return_value=config):
                                with patch("builtins.print"):
                                    result = check_config()
                                    self.assertFalse(result)

    def test_check_config_invalid_connection_types(self):
        """Test check_config with invalid Meshtastic connection types."""
        config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@test:matrix.org",
            },
            "matrix_rooms": [{"id": "!test:matrix.org"}],
            "meshtastic": {"connection_type": "invalid_type"},
        }

        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/test/config.yaml"]
            with patch("os.path.isfile", return_value=True):
                with patch("builtins.open", mock_open()):
                    with patch("yaml.load", return_value=config):
                        with patch("builtins.print") as mock_print:
                            result = check_config()
                            self.assertFalse(result)
                            mock_print.assert_called()

    def test_check_config_missing_connection_specific_fields(self):
        """Test check_config with missing connection-specific fields."""
        test_cases = [
            {"connection_type": "serial"},  # Missing serial_port
            {"connection_type": "tcp"},  # Missing host
            {"connection_type": "ble"},  # Missing ble_address
        ]

        for meshtastic_config in test_cases:
            with self.subTest(meshtastic_config=meshtastic_config):
                config = {
                    "matrix": {
                        "homeserver": "https://matrix.org",
                        "access_token": "test_token",
                        "bot_user_id": "@test:matrix.org",
                    },
                    "matrix_rooms": [{"id": "!test:matrix.org"}],
                    "meshtastic": meshtastic_config,
                }

                with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
                    mock_get_paths.return_value = ["/test/config.yaml"]
                    with patch("os.path.isfile", return_value=True):
                        with patch("builtins.open", mock_open()):
                            with patch("yaml.load", return_value=config):
                                with patch("builtins.print"):
                                    result = check_config()
                                    self.assertFalse(result)

    def test_generate_sample_config_existing_file(self):
        """Test generate_sample_config when config file already exists."""
        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/test/config.yaml"]
            with patch("os.path.isfile", return_value=True):
                with patch("builtins.print") as mock_print:
                    result = generate_sample_config()
                    self.assertFalse(result)
                    mock_print.assert_called()

    def test_generate_sample_config_directory_creation_failure(self):
        """Test generate_sample_config when directory creation fails."""
        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/readonly/config.yaml"]
            with patch("os.path.isfile", return_value=False):
                with patch(
                    "os.makedirs", side_effect=PermissionError("Permission denied")
                ):
                    with patch("builtins.print") as mock_print:
                        result = generate_sample_config()
                        self.assertFalse(result)
                        mock_print.assert_called()

    def test_generate_sample_config_missing_sample_file(self):
        """Test generate_sample_config when sample config file is missing."""
        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/test/config.yaml"]
            with patch("os.path.isfile", return_value=False):
                with patch("os.makedirs"):
                    with patch("mmrelay.tools.get_sample_config_path") as mock_get_sample:
                        mock_get_sample.return_value = "/nonexistent/sample.yaml"
                        with patch("mmrelay.cli.os.path.exists", return_value=False):
                            with patch("importlib.resources.files") as mock_resources:
                                mock_file = MagicMock()
                                mock_file.joinpath.return_value.read_text.side_effect = FileNotFoundError("Resource not found")
                                mock_resources.return_value = mock_file
                                with patch("builtins.print") as mock_print:
                                    result = generate_sample_config()
                                    self.assertFalse(result)
                                    mock_print.assert_called()

    def test_generate_sample_config_copy_failure(self):
        """Test generate_sample_config when file copy fails."""
        with patch("mmrelay.cli.get_config_paths") as mock_get_paths:
            mock_get_paths.return_value = ["/test/config.yaml"]
            with patch("os.path.isfile", return_value=False):
                with patch("os.makedirs"):
                    with patch("mmrelay.tools.get_sample_config_path") as mock_get_sample:
                        mock_get_sample.return_value = "/sample/config.yaml"
                        with patch("os.path.exists", return_value=True):
                            with patch(
                                "shutil.copy2", side_effect=IOError("Copy failed")
                            ):
                                with patch("builtins.print") as mock_print:
                                    result = generate_sample_config()
                                    self.assertFalse(result)
                                    mock_print.assert_called()

    def test_main_import_error_handling(self):
        """Test main function behavior when imports fail."""
        with patch("mmrelay.cli.parse_arguments") as mock_parse:
            args = MagicMock()
            args.check_config = False
            args.install_service = True
            args.generate_config = False
            args.version = False
            mock_parse.return_value = args

            # Mock import failure
            with patch(
                "builtins.__import__", side_effect=ImportError("Module not found")
            ):
                result = main()
                self.assertEqual(result, 1)

    def test_handle_cli_commands_service_installation_failure(self):
        """Test handle_cli_commands when service installation fails."""
        args = MagicMock()
        args.version = False
        args.install_service = True
        args.generate_config = False
        args.check_config = False

        with patch("mmrelay.setup_utils.install_service", return_value=False):
            with patch("sys.exit") as mock_exit:
                handle_cli_commands(args)
                mock_exit.assert_called_once_with(1)

    def test_handle_cli_commands_config_generation_failure(self):
        """Test handle_cli_commands when config generation fails."""
        args = MagicMock()
        args.version = False
        args.install_service = False
        args.generate_config = True
        args.check_config = False

        with patch("mmrelay.cli.generate_sample_config", return_value=False):
            with patch("sys.exit") as mock_exit:
                handle_cli_commands(args)
                mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
