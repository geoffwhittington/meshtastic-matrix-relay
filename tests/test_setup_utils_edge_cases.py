#!/usr/bin/env python3
"""
Test suite for Setup utilities edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- Service installation failures
- File permission errors
- System command failures
- Missing system dependencies
- Service file template errors
- User lingering configuration issues
- Path resolution edge cases
"""

import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.setup_utils import (
    check_lingering_enabled,
    check_loginctl_available,
    create_service_file,
    enable_lingering,
    get_executable_path,
    get_template_service_content,
    get_user_service_path,
    install_service,
    reload_daemon,
)


class TestSetupUtilsEdgeCases(unittest.TestCase):
    """Test cases for Setup utilities edge cases and error handling."""

    def test_get_user_service_path_permission_error(self):
        """Test get_user_service_path when directory creation fails."""
        with patch(
            "pathlib.Path.mkdir", side_effect=PermissionError("Permission denied")
        ):
            # Should not raise exception, just return the path
            result = get_user_service_path()
            self.assertIsInstance(result, Path)

    def test_get_executable_path_not_found(self):
        """Test get_executable_path when mmrelay executable is not found."""
        with patch("shutil.which", return_value=None):
            with patch("builtins.print"):  # Suppress warning print
                result = get_executable_path()
                # Should return sys.executable as fallback
                self.assertEqual(result, sys.executable)

    def test_get_executable_path_multiple_locations(self):
        """Test get_executable_path priority order."""

        def mock_which(cmd):
            if cmd == "mmrelay":
                return "/usr/local/bin/mmrelay"
            return None

        with patch("shutil.which", side_effect=mock_which):
            result = get_executable_path()
            self.assertEqual(result, "/usr/local/bin/mmrelay")

    def test_get_template_service_content_file_not_found(self):
        """Test get_template_service_content when template file doesn't exist."""
        with patch("mmrelay.setup_utils.get_template_service_path", return_value=None):
            result = get_template_service_content()
            # Should return default template
            self.assertIn("[Unit]", result)
            self.assertIn("Description=A Meshtastic", result)

    def test_get_template_service_content_read_error(self):
        """Test get_template_service_content when template file can't be read."""
        with patch("mmrelay.setup_utils.get_template_service_path", return_value="/test/service.template"):
            with patch("builtins.open", side_effect=IOError("Read error")):
                with patch("builtins.print") as mock_print:
                    result = get_template_service_content()
                    # Should return default template and print error
                    self.assertIn("[Unit]", result)
                    mock_print.assert_called()

    def test_create_service_file_write_permission_error(self):
        """Test create_service_file when writing fails due to permissions."""
        with patch("mmrelay.setup_utils.get_user_service_path") as mock_get_path:
            mock_path = MagicMock()
            mock_path.write_text.side_effect = PermissionError("Permission denied")
            mock_get_path.return_value = mock_path

            with patch(
                "mmrelay.setup_utils.get_template_service_content", return_value="[Unit]\nTest"
            ):
                with patch(
                    "mmrelay.setup_utils.get_executable_path",
                    return_value="/usr/bin/mmrelay",
                ):
                    with patch("builtins.print") as mock_print:
                        result = create_service_file()
                        self.assertFalse(result)
                        mock_print.assert_called()

    def test_create_service_file_no_executable(self):
        """Test create_service_file when executable path is not found."""
        with patch("mmrelay.setup_utils.get_executable_path", return_value=None):
            with patch("builtins.print") as mock_print:
                result = create_service_file()
                self.assertFalse(result)
                mock_print.assert_called()

    def test_reload_daemon_command_failure(self):
        """Test reload_daemon when systemctl command fails."""
        with patch("subprocess.run") as mock_run:
            # Mock subprocess.run to raise CalledProcessError (since check=True is used)
            mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl", "Command failed")

            with patch("builtins.print") as mock_print:
                result = reload_daemon()
                self.assertFalse(result)
                mock_print.assert_called()

    def test_reload_daemon_exception(self):
        """Test reload_daemon when subprocess raises exception."""
        with patch(
            "subprocess.run", side_effect=FileNotFoundError("systemctl not found")
        ):
            with patch("builtins.print") as mock_print:
                result = reload_daemon()
                self.assertFalse(result)
                mock_print.assert_called()

    def test_check_loginctl_available_not_found(self):
        """Test check_loginctl_available when loginctl is not available."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            result = check_loginctl_available()
            self.assertFalse(result)

    def test_check_loginctl_available_command_failure(self):
        """Test check_loginctl_available when loginctl command fails."""
        with patch("shutil.which", return_value="/usr/bin/loginctl"):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = Exception("Command failed")
                result = check_loginctl_available()
                self.assertFalse(result)

    def test_check_lingering_enabled_command_failure(self):
        """Test check_lingering_enabled when loginctl command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Command failed")
            with patch("builtins.print") as mock_print:
                result = check_lingering_enabled()
                self.assertFalse(result)
                mock_print.assert_called()

    def test_check_lingering_enabled_parsing_error(self):
        """Test check_lingering_enabled when output parsing fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "invalid output format"

            with patch("getpass.getuser", return_value="testuser"):
                result = check_lingering_enabled()
                self.assertFalse(result)

    def test_enable_lingering_command_failure(self):
        """Test enable_lingering when loginctl command fails."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Permission denied"

            with patch("builtins.print") as mock_print:
                result = enable_lingering()
                self.assertFalse(result)
                mock_print.assert_called()

    def test_enable_lingering_exception(self):
        """Test enable_lingering when subprocess raises exception."""
        with patch("subprocess.run", side_effect=Exception("Command failed")):
            with patch("builtins.print") as mock_print:
                result = enable_lingering()
                self.assertFalse(result)
                mock_print.assert_called()

    def test_install_service_no_executable(self):
        """Test install_service when executable is not found."""
        with patch("mmrelay.setup_utils.get_executable_path", return_value=None):
            with patch("builtins.print") as mock_print:
                result = install_service()
                self.assertFalse(result)
                mock_print.assert_called()

    def test_install_service_create_file_failure(self):
        """Test install_service when service file creation fails."""
        with patch(
            "mmrelay.setup_utils.get_executable_path", return_value="/usr/bin/mmrelay"
        ):
            with patch("mmrelay.setup_utils.create_service_file", return_value=False):
                with patch("builtins.print"):
                    result = install_service()
                    self.assertFalse(result)

    def test_install_service_daemon_reload_failure(self):
        """Test install_service when daemon reload fails."""
        with patch(
            "mmrelay.setup_utils.get_executable_path", return_value="/usr/bin/mmrelay"
        ):
            with patch("mmrelay.setup_utils.create_service_file", return_value=True):
                with patch(
                    "mmrelay.setup_utils.reload_daemon", return_value=False
                ):
                    with patch("mmrelay.setup_utils.read_service_file", return_value=None):
                        with patch("mmrelay.setup_utils.service_needs_update", return_value=(True, "test")):
                            with patch("mmrelay.setup_utils.check_loginctl_available", return_value=False):
                                with patch("builtins.input", return_value="n"):  # Mock all input prompts to return "n"
                                    with patch("builtins.print"):
                                        result = install_service()
                                        # Should still return True even if reload fails
                                        self.assertTrue(result)

    def test_install_service_lingering_check_failure(self):
        """Test install_service when lingering check fails."""
        with patch(
            "mmrelay.setup_utils.get_executable_path", return_value="/usr/bin/mmrelay"
        ):
            with patch("mmrelay.setup_utils.create_service_file", return_value=True):
                with patch(
                    "mmrelay.setup_utils.reload_daemon", return_value=True
                ):
                    with patch(
                        "mmrelay.setup_utils.check_loginctl_available",
                        return_value=True,
                    ):
                        with patch(
                            "mmrelay.setup_utils.check_lingering_enabled",
                            return_value=False,
                        ):
                            with patch("builtins.input", return_value="n"):
                                with patch("builtins.print") as mock_print:
                                    result = install_service()
                                    self.assertTrue(result)
                                    mock_print.assert_called()

    def test_install_service_enable_lingering_failure(self):
        """Test install_service when enabling lingering fails."""
        with patch(
            "mmrelay.setup_utils.get_executable_path", return_value="/usr/bin/mmrelay"
        ):
            with patch("mmrelay.setup_utils.create_service_file", return_value=True):
                with patch(
                    "mmrelay.setup_utils.reload_daemon", return_value=True
                ):
                    with patch(
                        "mmrelay.setup_utils.check_loginctl_available",
                        return_value=True,
                    ):
                        with patch(
                            "mmrelay.setup_utils.check_lingering_enabled",
                            return_value=False,
                        ):
                            with patch("builtins.input", return_value="y"):
                                with patch(
                                    "mmrelay.setup_utils.enable_lingering",
                                    return_value=False,
                                ):
                                    with patch("builtins.print"):
                                        result = install_service()
                                        self.assertTrue(result)  # Should still succeed

    def test_install_service_user_interaction_eof(self):
        """Test install_service when user input raises EOFError."""
        with patch(
            "mmrelay.setup_utils.get_executable_path", return_value="/usr/bin/mmrelay"
        ):
            with patch("mmrelay.setup_utils.create_service_file", return_value=True):
                with patch(
                    "mmrelay.setup_utils.reload_daemon", return_value=True
                ):
                    with patch(
                        "mmrelay.setup_utils.check_loginctl_available",
                        return_value=True,
                    ):
                        with patch(
                            "mmrelay.setup_utils.check_lingering_enabled",
                            return_value=False,
                        ):
                            with patch("builtins.input", side_effect=EOFError()):
                                with patch("builtins.print"):
                                    result = install_service()
                                    self.assertTrue(result)

    def test_install_service_user_interaction_keyboard_interrupt(self):
        """Test install_service when user input raises KeyboardInterrupt."""
        with patch(
            "mmrelay.setup_utils.get_executable_path", return_value="/usr/bin/mmrelay"
        ):
            with patch("mmrelay.setup_utils.create_service_file", return_value=True):
                with patch(
                    "mmrelay.setup_utils.reload_daemon", return_value=True
                ):
                    with patch(
                        "mmrelay.setup_utils.check_loginctl_available",
                        return_value=True,
                    ):
                        with patch(
                            "mmrelay.setup_utils.check_lingering_enabled",
                            return_value=False,
                        ):
                            with patch(
                                "builtins.input", side_effect=KeyboardInterrupt()
                            ):
                                with patch("builtins.print"):
                                    result = install_service()
                                    self.assertTrue(result)

    def test_service_template_placeholder_replacement(self):
        """Test that service template placeholders are properly replaced."""
        template = """
        WorkingDirectory=%h/meshtastic-matrix-relay
        ExecStart=%h/meshtastic-matrix-relay/.pyenv/bin/python %h/meshtastic-matrix-relay/main.py
        --config %h/.mmrelay/config/config.yaml
        """

        with patch("mmrelay.setup_utils.get_template_service_content", return_value=template):
            with patch(
                "mmrelay.setup_utils.get_executable_path",
                return_value="/usr/bin/mmrelay",
            ):
                with patch(
                    "mmrelay.setup_utils.get_user_service_path"
                ) as mock_get_path:
                    mock_path = MagicMock()
                    mock_get_path.return_value = mock_path

                    result = create_service_file()
                    self.assertTrue(result)

                    # Check that placeholders were replaced
                    written_content = mock_path.write_text.call_args[0][0]
                    self.assertNotIn("%h/meshtastic-matrix-relay", written_content)
                    self.assertIn("/usr/bin/mmrelay", written_content)
                    self.assertIn("--config %h/.mmrelay/config.yaml", written_content)


if __name__ == "__main__":
    unittest.main()
