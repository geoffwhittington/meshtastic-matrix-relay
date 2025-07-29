import os
import sys
import unittest
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.config import (
    get_base_dir,
    get_config_paths,
    get_data_dir,
    get_log_dir,
    get_plugin_data_dir,
    load_config,
)


import mmrelay.config


class TestConfig(unittest.TestCase):
    def setUp(self):
        # Reset the global config before each test
        mmrelay.config.relay_config = {}
        mmrelay.config.config_path = None

    def test_get_base_dir_linux(self):
        # Test default base dir on Linux
        with patch("sys.platform", "linux"):
            base_dir = get_base_dir()
            self.assertEqual(base_dir, os.path.expanduser("~/.mmrelay"))

    @patch("platformdirs.user_data_dir")
    def test_get_base_dir_windows(self, mock_user_data_dir):
        # Test default base dir on Windows
        with patch("sys.platform", "win32"):
            mock_user_data_dir.return_value = "C:\\Users\\test\\AppData\\Local\\mmrelay"
            base_dir = get_base_dir()
            self.assertEqual(base_dir, "C:\\Users\\test\\AppData\\Local\\mmrelay")

    @patch("mmrelay.config.os.path.isfile")
    @patch("builtins.open")
    @patch("mmrelay.config.yaml.load")
    def test_load_config_from_file(self, mock_yaml_load, mock_open, mock_isfile):
        # Mock a config file
        mock_yaml_load.return_value = {"key": "value"}
        mock_isfile.return_value = True

        # Test loading from a specific path
        config = load_config(config_file="myconfig.yaml")
        self.assertEqual(config, {"key": "value"})

    @patch("mmrelay.config.os.path.isfile")
    def test_load_config_not_found(self, mock_isfile):
        # Mock no config file found
        mock_isfile.return_value = False

        # Test that it returns an empty dict
        with patch("sys.argv", ["mmrelay"]):
            config = load_config()
            self.assertEqual(config, {})

    def test_get_config_paths_linux(self):
        # Test with no args on Linux
        with patch("sys.platform", "linux"), patch("sys.argv", ["mmrelay"]):
            paths = get_config_paths()
            self.assertIn(os.path.expanduser("~/.mmrelay/config.yaml"), paths)

    @patch("platformdirs.user_config_dir")
    def test_get_config_paths_windows(self, mock_user_config_dir):
        # Test with no args on Windows
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
        with patch("sys.platform", "linux"):
            data_dir = get_data_dir()
            self.assertEqual(data_dir, os.path.expanduser("~/.mmrelay/data"))

    def test_get_log_dir_linux(self):
        with patch("sys.platform", "linux"):
            log_dir = get_log_dir()
            self.assertEqual(log_dir, os.path.expanduser("~/.mmrelay/logs"))

    def test_get_plugin_data_dir_linux(self):
        with patch("sys.platform", "linux"):
            plugin_data_dir = get_plugin_data_dir()
            self.assertEqual(
                plugin_data_dir, os.path.expanduser("~/.mmrelay/data/plugins")
            )
            plugin_specific_dir = get_plugin_data_dir("my_plugin")
            self.assertEqual(
                plugin_specific_dir,
                os.path.expanduser("~/.mmrelay/data/plugins/my_plugin"),
            )


if __name__ == "__main__":
    unittest.main()
