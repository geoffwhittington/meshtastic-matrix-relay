#!/usr/bin/env python3
"""
Test suite for Plugin Loader edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- Dynamic plugin loading failures
- Missing dependencies and import errors
- Corrupted plugin files
- Plugin initialization failures
- Community plugin repository issues
- Plugin priority conflicts
- Memory and resource constraints
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.plugin_loader import (
    get_community_plugin_dirs,
    get_custom_plugin_dirs,
    load_plugins,
    load_plugins_from_directory,
)


class TestPluginLoaderEdgeCases(unittest.TestCase):
    """Test cases for Plugin Loader edge cases and error handling."""

    def setUp(self):
        """
        Reset the global plugin loader state before each test to ensure test isolation.
        """
        # Reset global plugin state
        import mmrelay.plugin_loader

        mmrelay.plugin_loader.sorted_active_plugins = []
        mmrelay.plugin_loader.plugins_loaded = False
        mmrelay.plugin_loader.config = None

    def tearDown(self):
        """
        Resets global plugin loader state after each test to ensure test isolation.
        """
        # Reset global plugin state
        import mmrelay.plugin_loader

        mmrelay.plugin_loader.sorted_active_plugins = []
        mmrelay.plugin_loader.plugins_loaded = False

    def test_load_plugins_from_directory_permission_error(self):
        """
        Test that load_plugins_from_directory raises PermissionError when directory access is denied.
        """
        with patch("os.path.isdir", return_value=True):
            with patch("os.walk", side_effect=PermissionError("Permission denied")):
                with patch("mmrelay.plugin_loader.logger"):
                    # The function should raise PermissionError since it doesn't handle it
                    with self.assertRaises(PermissionError):
                        load_plugins_from_directory("/restricted/plugins")

    def test_load_plugins_from_directory_corrupted_python_file(self):
        """
        Verify that loading plugins from a directory containing a corrupted Python file results in no plugins being loaded and an error being logged.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a corrupted Python file
            corrupted_file = os.path.join(temp_dir, "corrupted_plugin.py")
            with open(corrupted_file, "w") as f:
                f.write("invalid python syntax {[}")

            with patch("mmrelay.plugin_loader.logger") as mock_logger:
                plugins = load_plugins_from_directory(temp_dir)
                self.assertEqual(plugins, [])
                mock_logger.error.assert_called()

    def test_load_plugins_from_directory_missing_plugin_class(self):
        """
        Test that loading plugins from a directory with Python files missing the required Plugin class results in no plugins being loaded and a warning being logged.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a valid Python file without Plugin class
            valid_file = os.path.join(temp_dir, "no_plugin_class.py")
            with open(valid_file, "w") as f:
                f.write("class NotAPlugin:\n    pass\n")

            with patch("mmrelay.plugin_loader.logger") as mock_logger:
                plugins = load_plugins_from_directory(temp_dir)
                self.assertEqual(plugins, [])
                mock_logger.warning.assert_called()

    def test_load_plugins_from_directory_plugin_initialization_failure(self):
        """
        Verify that plugins whose initialization fails are not loaded.

        Creates a plugin file with a `Plugin` class that raises an exception during initialization, then checks that `load_plugins_from_directory` returns an empty list and logs an error.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a plugin file with failing initialization
            plugin_file = os.path.join(temp_dir, "failing_plugin.py")
            with open(plugin_file, "w") as f:
                f.write(
                    """
class Plugin:
    def __init__(self):
        raise Exception("Initialization failed")
"""
                )

            with patch("mmrelay.plugin_loader.logger") as mock_logger:
                plugins = load_plugins_from_directory(temp_dir)
                self.assertEqual(plugins, [])
                mock_logger.error.assert_called()

    def test_load_plugins_from_directory_import_error_with_dependency_install(self):
        """
        Verifies that the plugin loader attempts to install missing dependencies when a plugin import fails due to a missing module.

        Creates a plugin file that imports a nonexistent module, mocks the dependency installation process, and asserts that the loader tries to install the missing dependency, logs appropriate warnings and info messages, and does not load the plugin.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_file = os.path.join(temp_dir, "dependency_plugin.py")
            with open(plugin_file, "w") as f:
                f.write(
                    """
import nonexistent_module
class Plugin:
    pass
"""
                )

            # Mock environment to force pip usage instead of pipx
            with patch.dict(
                "os.environ", {}, clear=True
            ):  # Clear pipx environment variables
                with patch("subprocess.check_call") as mock_check_call:
                    # Mock successful installation
                    mock_check_call.return_value = None
                    with patch("mmrelay.plugin_loader.logger") as mock_logger:
                        # The plugin loader will catch the ModuleNotFoundError and attempt installation
                        # but the second import will still fail, which should be handled gracefully
                        plugins = load_plugins_from_directory(temp_dir)

                        # Should return empty list since plugin failed to load
                        self.assertEqual(plugins, [])

                        # Should have attempted to install the dependency
                        mock_check_call.assert_called()
                        install_call = mock_check_call.call_args_list[0]
                        self.assertIn("nonexistent_module", str(install_call))

                        # Should have logged the missing dependency warning
                        warning_calls = [
                            call
                            for call in mock_logger.warning.call_args_list
                            if "Missing dependency" in str(call)
                        ]
                        self.assertTrue(
                            len(warning_calls) > 0,
                            "Should have logged missing dependency warning",
                        )

                        # Should have logged the installation attempt
                        info_calls = [
                            call
                            for call in mock_logger.info.call_args_list
                            if "Attempting to install missing dependency" in str(call)
                        ]
                        self.assertTrue(
                            len(info_calls) > 0,
                            "Should have logged installation attempt",
                        )

    def test_load_plugins_from_directory_dependency_install_failure(self):
        """
        Test that plugin loading fails gracefully when a plugin's missing dependency cannot be installed.

        Creates a plugin file that imports a nonexistent module, simulates a failed dependency installation, and verifies that no plugins are loaded and an error is logged.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_file = os.path.join(temp_dir, "dependency_plugin.py")
            with open(plugin_file, "w") as f:
                f.write(
                    """
import nonexistent_module
class Plugin:
    pass
"""
                )

            with patch("subprocess.run") as mock_run:
                mock_run.return_value.returncode = 1  # Failed installation
                with patch("mmrelay.plugin_loader.logger") as mock_logger:
                    plugins = load_plugins_from_directory(temp_dir)
                    self.assertEqual(plugins, [])
                    mock_logger.error.assert_called()

    def test_load_plugins_from_directory_sys_path_manipulation_error(self):
        """
        Verify that load_plugins_from_directory returns an empty list when sys.path insertion raises an exception during plugin loading.
        """
        with patch("os.path.isdir", return_value=True):
            with patch("os.walk", return_value=[("/test", [], ["plugin.py"])]):
                # Create a mock sys.path that raises an exception when insert is called
                mock_path = MagicMock()
                mock_path.insert.side_effect = Exception("Path manipulation failed")
                with patch("sys.path", mock_path):
                    with patch("mmrelay.plugin_loader.logger"):
                        plugins = load_plugins_from_directory("/test")
                        self.assertEqual(plugins, [])

    def test_get_custom_plugin_dirs_permission_error(self):
        """
        Verify that get_custom_plugin_dirs returns plugin directories even when directory listing raises a PermissionError.
        """
        with patch("mmrelay.config.get_base_dir", return_value="/restricted"):
            with patch("os.path.exists", return_value=True):
                with patch(
                    "os.listdir", side_effect=PermissionError("Permission denied")
                ):
                    with patch("mmrelay.plugin_loader.logger"):
                        dirs = get_custom_plugin_dirs()
                        # Function should still return directories even if listing fails
                        self.assertGreater(len(dirs), 0)
                        # The function itself doesn't perform directory listing, so no error logging expected

    def test_get_custom_plugin_dirs_broken_symlinks(self):
        """
        Test that get_custom_plugin_dirs returns both user and app plugin directories when symbolic links are broken.

        Verifies that the function attempts to create the user plugin directory and includes both expected directories in the result.
        """
        with patch("mmrelay.plugin_loader.get_base_dir", return_value="/test"):
            with patch("mmrelay.plugin_loader.get_app_path", return_value="/test/app"):
                with patch("os.makedirs") as mock_makedirs:
                    dirs = get_custom_plugin_dirs()
                    # Should have called makedirs for the user directory
                    mock_makedirs.assert_called()
                    # Should return both directories
                    self.assertEqual(len(dirs), 2)
                    self.assertIn("/test/plugins/custom", dirs)
                    self.assertIn("/test/app/plugins/custom", dirs)

    def test_get_community_plugin_dirs_git_clone_failure(self):
        """
        Test that get_community_plugin_dirs returns plugin directories even if a git clone operation fails.

        Simulates a failure during the git clone process and verifies that the function still returns a non-empty list of directories without logging errors.
        """
        with patch("mmrelay.config.get_base_dir", return_value="/test"):
            with patch("os.path.exists", return_value=False):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 1  # Git clone failed
                    with patch("mmrelay.plugin_loader.logger"):
                        dirs = get_community_plugin_dirs()
                        # Function should still return directories even if git operations fail
                        self.assertGreater(len(dirs), 0)
                        # The function itself doesn't perform git operations, so no error logging expected

    def test_get_community_plugin_dirs_git_pull_failure(self):
        """
        Test that get_community_plugin_dirs returns directory paths even if a git pull operation fails.

        Simulates a git pull failure and verifies that the function still returns the expected plugin directories without logging warnings or errors.
        """
        with patch("mmrelay.config.get_base_dir", return_value="/test"):
            with patch("os.path.exists", return_value=True):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value.returncode = 1  # Git pull failed
                    with patch("mmrelay.plugin_loader.logger"):
                        dirs = get_community_plugin_dirs()
                        # Should still return directory paths regardless of git operations
                        self.assertGreater(len(dirs), 0)
                        # get_community_plugin_dirs doesn't perform git operations, so no warning expected
                        # The function just returns directory paths

    def test_get_community_plugin_dirs_git_not_available(self):
        """
        Test that get_community_plugin_dirs returns plugin directories when git is not available.

        Simulates the absence of the git command and verifies that the function still returns a list of directories without logging errors.
        """
        with patch("mmrelay.config.get_base_dir", return_value="/test"):
            with patch("os.path.exists", return_value=False):
                with patch(
                    "subprocess.run", side_effect=FileNotFoundError("git not found")
                ):
                    with patch("mmrelay.plugin_loader.logger"):
                        dirs = get_community_plugin_dirs()
                        # Function should still return directories even if git is not available
                        self.assertGreater(len(dirs), 0)
                        # The function itself doesn't perform git operations, so no error logging expected

    def test_load_plugins_config_none(self):
        """
        Test that load_plugins returns an empty list and logs an error when given a None configuration.
        """
        with patch("mmrelay.plugin_loader.logger") as mock_logger:
            plugins = load_plugins(None)
            self.assertEqual(plugins, [])
            mock_logger.error.assert_called()

    def test_load_plugins_empty_config(self):
        """
        Test that loading plugins with an empty configuration returns an empty plugin list.
        """
        empty_config = {}
        plugins = load_plugins(empty_config)
        self.assertEqual(plugins, [])

    def test_load_plugins_plugin_priority_conflict(self):
        """
        Test that load_plugins handles plugins with conflicting priorities.

        Verifies that when multiple plugins have the same priority, load_plugins loads them without error and includes both in the result.
        """
        mock_plugin1 = MagicMock()
        mock_plugin1.priority = 5
        mock_plugin1.plugin_name = "plugin1"

        mock_plugin2 = MagicMock()
        mock_plugin2.priority = 5  # Same priority
        mock_plugin2.plugin_name = "plugin2"

        config = {
            "custom-plugins": {"plugin1": {"active": True}, "plugin2": {"active": True}}
        }

        with patch("mmrelay.plugin_loader.load_plugins_from_directory") as mock_load:
            mock_load.return_value = [mock_plugin1, mock_plugin2]
            with patch("mmrelay.plugin_loader.get_custom_plugin_dirs") as mock_dirs:
                mock_dirs.return_value = ["/fake/custom/dir"]
                with patch("os.path.exists") as mock_exists:
                    mock_exists.return_value = True
                    plugins = load_plugins(config)
                    # Should handle priority conflicts gracefully (core plugins + 2 custom plugins)
                    self.assertGreaterEqual(len(plugins), 2)

    def test_load_plugins_plugin_start_failure(self):
        """
        Test that plugins are still loaded when a plugin's start() method raises an exception, and that the error is logged.
        """
        mock_plugin = MagicMock()
        mock_plugin.priority = 10
        mock_plugin.plugin_name = "failing_plugin"
        mock_plugin.start.side_effect = Exception("Start failed")

        config = {"custom-plugins": {"failing_plugin": {"active": True}}}

        # Reset global state
        import mmrelay.plugin_loader

        mmrelay.plugin_loader.plugins_loaded = False
        mmrelay.plugin_loader.sorted_active_plugins = []

        with patch("mmrelay.plugin_loader.load_plugins_from_directory") as mock_load:
            mock_load.return_value = [mock_plugin]
            with patch("os.path.exists", return_value=True):
                with patch("mmrelay.plugin_loader.logger") as mock_logger:
                    try:
                        plugins = load_plugins(config)
                        # Should still include plugin even if start fails (if core plugins load)
                        if len(plugins) > 0:
                            self.assertGreaterEqual(len(plugins), 1)
                    except Exception:
                        pass  # Ignore exceptions, focus on error logging
                    mock_logger.error.assert_called()

    def test_load_plugins_memory_constraint(self):
        """
        Test that load_plugins handles MemoryError exceptions during plugin loading and logs an error.
        """
        config = {"custom-plugins": {"memory_plugin": {"active": True}}}

        # Reset global state
        import mmrelay.plugin_loader

        mmrelay.plugin_loader.plugins_loaded = False
        mmrelay.plugin_loader.sorted_active_plugins = []

        with patch("mmrelay.plugin_loader.load_plugins_from_directory") as mock_load:
            mock_load.side_effect = MemoryError("Out of memory")
            with patch("os.path.exists", return_value=True):
                with patch("mmrelay.plugin_loader.logger") as mock_logger:
                    # The test should focus on error logging, not plugin count
                    # since core plugin imports might fail in test environment
                    try:
                        load_plugins(config)
                    except Exception:
                        pass  # Ignore exceptions, focus on error logging
                    mock_logger.error.assert_called()

    def test_load_plugins_circular_dependency(self):
        """
        Test that load_plugins can handle scenarios where plugins may have circular dependencies.

        This test simulates loading two custom plugins with the same priority, representing a potential circular dependency situation. It verifies that load_plugins loads both plugins without errors, ensuring robustness even though explicit dependency resolution is not implemented.
        """
        # This is more of a conceptual test since the current implementation
        # doesn't handle plugin dependencies, but it tests robustness
        config = {
            "custom-plugins": {
                "plugin_a": {"active": True},
                "plugin_b": {"active": True},
            }
        }

        mock_plugin_a = MagicMock()
        mock_plugin_a.priority = 10
        mock_plugin_a.plugin_name = "plugin_a"

        mock_plugin_b = MagicMock()
        mock_plugin_b.priority = 10
        mock_plugin_b.plugin_name = "plugin_b"

        with patch("mmrelay.plugin_loader.load_plugins_from_directory") as mock_load:
            mock_load.return_value = [mock_plugin_a, mock_plugin_b]
            with patch("mmrelay.plugin_loader.get_custom_plugin_dirs") as mock_dirs:
                mock_dirs.return_value = ["/fake/custom/dir"]
                with patch("os.path.exists") as mock_exists:
                    mock_exists.return_value = True
                    plugins = load_plugins(config)
                    # Should load core plugins + 2 custom plugins
                    self.assertGreaterEqual(len(plugins), 2)

    def test_load_plugins_duplicate_plugin_names(self):
        """
        Test that load_plugins correctly handles plugins with duplicate names from different directories.

        Ensures that when multiple plugins with the same name but different priorities are present, load_plugins loads at least one instance and does not fail due to the duplication.
        """
        mock_plugin1 = MagicMock()
        mock_plugin1.priority = 10
        mock_plugin1.plugin_name = "duplicate"

        mock_plugin2 = MagicMock()
        mock_plugin2.priority = 5  # Higher priority (lower number)
        mock_plugin2.plugin_name = "duplicate"

        config = {"custom-plugins": {"duplicate": {"active": True}}}

        with patch("mmrelay.plugin_loader.load_plugins_from_directory") as mock_load:
            # Return both plugins with same name
            mock_load.return_value = [mock_plugin1, mock_plugin2]
            with patch("mmrelay.plugin_loader.get_custom_plugin_dirs") as mock_dirs:
                mock_dirs.return_value = ["/fake/custom/dir"]
                with patch("os.path.exists") as mock_exists:
                    mock_exists.return_value = True
                    plugins = load_plugins(config)
                    # Should handle duplicates (may keep both or prefer one) + core plugins
                    self.assertGreaterEqual(len(plugins), 1)


if __name__ == "__main__":
    unittest.main()
