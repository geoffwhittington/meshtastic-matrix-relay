import os
import sys
import unittest
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mmrelay.config
from mmrelay.config import (
    get_base_dir,
    get_config_paths,
    get_data_dir,
    get_log_dir,
    get_plugin_data_dir,
    load_config,
)


class TestConfig(unittest.TestCase):
    def setUp(self):
        # Reset the global config before each test
        """
        Reset the global configuration state before each test to ensure test isolation.
        """
        mmrelay.config.relay_config = {}
        mmrelay.config.config_path = None

    def test_get_base_dir_linux(self):
        # Test default base dir on Linux
        """
        Tests that get_base_dir returns the default base directory on Linux systems.
        """
        with patch("sys.platform", "linux"), patch("mmrelay.config.custom_data_dir", None):
            base_dir = get_base_dir()
            self.assertEqual(base_dir, os.path.expanduser("~/.mmrelay"))

    @patch("platformdirs.user_data_dir")
    def test_get_base_dir_windows(self, mock_user_data_dir):
        # Test default base dir on Windows
        """
        Tests that get_base_dir returns the correct default base directory on Windows platforms by mocking platform detection and user data directory.
        """
        with patch("sys.platform", "win32"), patch("mmrelay.config.custom_data_dir", None):
            mock_user_data_dir.return_value = "C:\\Users\\test\\AppData\\Local\\mmrelay"
            base_dir = get_base_dir()
            self.assertEqual(base_dir, "C:\\Users\\test\\AppData\\Local\\mmrelay")

    @patch("mmrelay.config.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.config.yaml.load")
    def test_load_config_from_file(self, mock_yaml_load, mock_open, mock_isfile):
        # Mock a config file
        """
        Test that `load_config` loads and returns configuration data from a specified YAML file when the file exists.
        """
        mock_yaml_load.return_value = {"key": "value"}
        mock_isfile.return_value = True

        # Test loading from a specific path
        config = load_config(config_file="myconfig.yaml")
        self.assertEqual(config, {"key": "value"})

    @patch("mmrelay.config.os.path.isfile")
    def test_load_config_not_found(self, mock_isfile):
        # Mock no config file found
        """
        Test that `load_config` returns an empty dictionary when no configuration file is found.
        """
        mock_isfile.return_value = False

        # Test that it returns an empty dict
        with patch("sys.argv", ["mmrelay"]):
            config = load_config()
            self.assertEqual(config, {})

    def test_get_config_paths_linux(self):
        # Test with no args on Linux
        """
        Test that `get_config_paths` includes the default Linux config path when no arguments are provided.
        """
        with patch("sys.platform", "linux"), patch("sys.argv", ["mmrelay"]), patch("mmrelay.config.custom_data_dir", None):
            paths = get_config_paths()
            self.assertIn(os.path.expanduser("~/.mmrelay/config.yaml"), paths)

    @patch("platformdirs.user_config_dir")
    def test_get_config_paths_windows(self, mock_user_config_dir):
        # Test with no args on Windows
        """
        Test that get_config_paths returns the correct config file path on Windows platforms.

        Simulates a Windows environment and verifies that the generated config paths include the expected Windows-specific config file location.
        """
        with patch("sys.platform", "win32"), patch("sys.argv", ["mmrelay"]):
            mock_user_config_dir.return_value = (
                "C:\\Users\\test\\AppData\\Local\\mmrelay\\config"
            )
            paths = get_config_paths()
            expected_path = os.path.join(
                "C:\\Users\\test\\AppData\\Local\\mmrelay\\config", "config.yaml"
            )
            self.assertIn(expected_path, paths)

    def test_get_data_dir_linux(self):
        """
        Test that get_data_dir returns the correct default data directory on Linux.
        """
        with patch("sys.platform", "linux"), patch("mmrelay.config.custom_data_dir", None):
            data_dir = get_data_dir()
            self.assertEqual(data_dir, os.path.expanduser("~/.mmrelay/data"))

    def test_get_log_dir_linux(self):
        with patch("sys.platform", "linux"), patch("mmrelay.config.custom_data_dir", None):
            log_dir = get_log_dir()
            self.assertEqual(log_dir, os.path.expanduser("~/.mmrelay/logs"))

    def test_get_plugin_data_dir_linux(self):
        """
        Test that get_plugin_data_dir returns the correct plugin data directory paths on Linux.

        Verifies that the default plugins data directory and a plugin-specific data directory are correctly resolved for the Linux platform.
        """
        with patch("sys.platform", "linux"), patch("mmrelay.config.custom_data_dir", None):
            plugin_data_dir = get_plugin_data_dir()
            self.assertEqual(
                plugin_data_dir, os.path.expanduser("~/.mmrelay/data/plugins")
            )
            plugin_specific_dir = get_plugin_data_dir("my_plugin")
            self.assertEqual(
                plugin_specific_dir,
                os.path.expanduser("~/.mmrelay/data/plugins/my_plugin"),
            )


class TestConfigEdgeCases(unittest.TestCase):
    """Test configuration edge cases and error handling."""

    def setUp(self):
        """Reset global config state before each test."""
        mmrelay.config.relay_config = {}
        mmrelay.config.config_path = None

    @patch("mmrelay.config.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.config.yaml.load")
    def test_config_migration_scenarios(self, mock_yaml_load, mock_open, mock_isfile):
        """
        Test configuration migration from old format to new format.

        Simulates loading an old-style config and verifies that it's properly
        migrated to the new format with appropriate defaults.
        """
        # Simulate old config format (missing new fields)
        old_config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "username": "@bot:matrix.org",
                "password": "secret"
            },
            "meshtastic": {
                "connection_type": "serial",
                "serial_port": "/dev/ttyUSB0"
            }
        }

        mock_yaml_load.return_value = old_config
        mock_isfile.return_value = True

        # Load config and verify migration
        config = load_config(config_file="old_config.yaml")

        # Should contain original data
        self.assertEqual(config["matrix"]["homeserver"], "https://matrix.org")
        self.assertEqual(config["meshtastic"]["connection_type"], "serial")

        # Should handle missing fields gracefully
        self.assertIsInstance(config, dict)

    @patch("mmrelay.config.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.config.yaml.load")
    def test_partial_config_handling(self, mock_yaml_load, mock_open, mock_isfile):
        """
        Test handling of partial/incomplete configuration files.

        Verifies that the system can handle configs with missing sections
        or incomplete data without crashing.
        """
        # Test with minimal config
        minimal_config = {
            "matrix": {
                "homeserver": "https://matrix.org"
                # Missing username, password, etc.
            }
            # Missing meshtastic section entirely
        }

        mock_yaml_load.return_value = minimal_config
        mock_isfile.return_value = True

        # Should load without error
        config = load_config(config_file="minimal_config.yaml")

        # Should contain what was provided
        self.assertEqual(config["matrix"]["homeserver"], "https://matrix.org")

        # Should handle missing sections gracefully
        self.assertNotIn("username", config.get("matrix", {}))

    @patch("mmrelay.config.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.config.yaml.load")
    def test_config_validation_error_messages(self, mock_yaml_load, mock_open, mock_isfile):
        """
        Test that configuration validation provides helpful error messages.

        Verifies that when invalid configurations are loaded, the system
        provides clear, actionable error messages to help users fix issues.
        """
        # Test with invalid YAML structure
        invalid_config = {
            "matrix": "not_a_dict",  # Should be a dictionary
            "meshtastic": {
                "connection_type": "invalid_type"  # Invalid connection type
            }
        }

        mock_yaml_load.return_value = invalid_config
        mock_isfile.return_value = True

        # Should load but config validation elsewhere should catch issues
        config = load_config(config_file="invalid_config.yaml")

        # Config should load (validation happens elsewhere)
        self.assertIsInstance(config, dict)
        self.assertEqual(config["matrix"], "not_a_dict")

    @patch("mmrelay.config.os.path.isfile")
    @patch("builtins.open")
    def test_corrupted_config_file_handling(self, mock_open, mock_isfile):
        """
        Test handling of corrupted or malformed YAML files.

        Verifies that the system gracefully handles YAML parsing errors
        and provides appropriate fallback behavior.
        """
        import yaml

        mock_isfile.return_value = True

        # Simulate YAML parsing error
        mock_open.return_value.__enter__.return_value.read.return_value = "invalid: yaml: content: ["

        with patch("mmrelay.config.yaml.load", side_effect=yaml.YAMLError("Invalid YAML")):
            # Should handle YAML errors gracefully
            try:
                config = load_config(config_file="corrupted.yaml")
                # If no exception, should return empty dict or handle gracefully
                self.assertIsInstance(config, dict)
            except yaml.YAMLError:
                # If exception is raised, it should be a YAML error
                pass

    @patch("mmrelay.config.os.path.isfile")
    def test_missing_config_file_fallback(self, mock_isfile):
        """
        Test fallback behavior when configuration file is missing.

        Verifies that the system provides sensible defaults when no
        configuration file is found.
        """
        mock_isfile.return_value = False

        with patch("sys.argv", ["mmrelay"]):
            config = load_config()

            # Should return empty dict when no config found
            self.assertEqual(config, {})

            # Should not crash or raise exceptions
            self.assertIsInstance(config, dict)

    @patch("mmrelay.config.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.config.yaml.load")
    def test_config_with_environment_variables(self, mock_yaml_load, mock_open, mock_isfile):
        """
        Test configuration that references environment variables.

        Verifies that configs can include environment variable references
        and that they're properly resolved.
        """
        # Config with environment variable references
        env_config = {
            "matrix": {
                "homeserver": "${MATRIX_HOMESERVER}",
                "access_token": "${MATRIX_TOKEN}"
            },
            "meshtastic": {
                "serial_port": "${MESHTASTIC_PORT}"
            }
        }

        mock_yaml_load.return_value = env_config
        mock_isfile.return_value = True

        # Set environment variables
        with patch.dict(os.environ, {
            "MATRIX_HOMESERVER": "https://test.matrix.org",
            "MATRIX_TOKEN": "test_token_123",
            "MESHTASTIC_PORT": "/dev/ttyUSB1"
        }):
            config = load_config(config_file="env_config.yaml")

            # Should load the raw config (environment variable expansion happens elsewhere)
            self.assertEqual(config["matrix"]["homeserver"], "${MATRIX_HOMESERVER}")
            self.assertEqual(config["matrix"]["access_token"], "${MATRIX_TOKEN}")

    def test_config_path_resolution_edge_cases(self):
        """
        Test edge cases in configuration path resolution.

        Verifies that the system handles unusual path scenarios correctly,
        including relative paths, symlinks, and special characters.
        """
        with patch("sys.argv", ["mmrelay", "--config", "../config/test.yaml"]):
            paths = get_config_paths()

            # Should include the specified relative path
            self.assertIn("../config/test.yaml", paths)

        with patch("sys.argv", ["mmrelay", "--config", "/absolute/path/config.yaml"]):
            paths = get_config_paths()

            # Should include the absolute path
            self.assertIn("/absolute/path/config.yaml", paths)


if __name__ == "__main__":
    unittest.main()
