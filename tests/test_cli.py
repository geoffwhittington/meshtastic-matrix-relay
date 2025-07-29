import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.cli import check_config, parse_arguments


class TestCLI(unittest.TestCase):
    def test_parse_arguments(self):
        # Test with no arguments
        with patch("sys.argv", ["mmrelay"]):
            args = parse_arguments()
            self.assertIsNone(args.config)
            self.assertIsNone(args.data_dir)
            self.assertIsNone(args.log_level)
            self.assertIsNone(args.logfile)
            self.assertFalse(args.version)
            self.assertFalse(args.generate_config)
            self.assertFalse(args.install_service)
            self.assertFalse(args.check_config)

        # Test with all arguments
        with patch(
            "sys.argv",
            [
                "mmrelay",
                "--config",
                "myconfig.yaml",
                "--data-dir",
                "/my/data",
                "--log-level",
                "debug",
                "--logfile",
                "/my/log.txt",
                "--version",
                "--generate-config",
                "--install-service",
                "--check-config",
            ],
        ):
            args = parse_arguments()
            self.assertEqual(args.config, "myconfig.yaml")
            self.assertEqual(args.data_dir, "/my/data")
            self.assertEqual(args.log_level, "debug")
            self.assertEqual(args.logfile, "/my/log.txt")
            self.assertTrue(args.version)
            self.assertTrue(args.generate_config)
            self.assertTrue(args.install_service)
            self.assertTrue(args.check_config)

    @patch("mmrelay.cli.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.cli.yaml.load")
    def test_check_config_valid(self, mock_yaml_load, mock_open, mock_isfile):
        # Mock a valid config
        mock_yaml_load.return_value = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "token",
                "bot_user_id": "@bot:matrix.org",
            },
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"},
        }
        mock_isfile.return_value = True

        with patch("sys.argv", ["mmrelay", "--config", "valid_config.yaml"]):
            self.assertTrue(check_config())

    @patch("mmrelay.cli.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.cli.yaml.load")
    def test_check_config_invalid_missing_matrix(
        self, mock_yaml_load, mock_open, mock_isfile
    ):
        # Mock an invalid config (missing matrix section)
        mock_yaml_load.return_value = {
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
            "meshtastic": {"connection_type": "serial", "serial_port": "/dev/ttyUSB0"},
        }
        mock_isfile.return_value = True

        with patch("sys.argv", ["mmrelay", "--config", "invalid_config.yaml"]):
            self.assertFalse(check_config())

    @patch("mmrelay.cli.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.cli.yaml.load")
    def test_check_config_invalid_missing_meshtastic(
        self, mock_yaml_load, mock_open, mock_isfile
    ):
        # Mock an invalid config (missing meshtastic section)
        mock_yaml_load.return_value = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "token",
                "bot_user_id": "@bot:matrix.org",
            },
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
        }
        mock_isfile.return_value = True

        with patch("sys.argv", ["mmrelay", "--config", "invalid_config.yaml"]):
            self.assertFalse(check_config())

    @patch("mmrelay.cli.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.cli.yaml.load")
    def test_check_config_invalid_connection_type(
        self, mock_yaml_load, mock_open, mock_isfile
    ):
        # Mock an invalid config (invalid connection type)
        mock_yaml_load.return_value = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "token",
                "bot_user_id": "@bot:matrix.org",
            },
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
            "meshtastic": {"connection_type": "invalid"},
        }
        mock_isfile.return_value = True

        with patch("sys.argv", ["mmrelay", "--config", "invalid_config.yaml"]):
            self.assertFalse(check_config())


if __name__ == "__main__":
    unittest.main()
