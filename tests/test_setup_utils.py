#!/usr/bin/env python3
"""
Test suite for setup utilities in MMRelay.

Tests the service installation and management functionality including:
- Service file creation and template handling
- Systemd user service management
- Executable path detection
- Service status checking and control
- User lingering configuration
- Service file update detection
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.setup_utils import (
    check_lingering_enabled,
    create_service_file,
    enable_lingering,
    get_executable_path,
    get_template_service_content,
    get_template_service_path,
    get_user_service_path,
    install_service,
    is_service_active,
    is_service_enabled,
    read_service_file,
    reload_daemon,
    service_exists,
    service_needs_update,
    show_service_status,
    start_service,
)


class TestSetupUtils(unittest.TestCase):
    """Test cases for setup utilities."""

    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for testing
        self.test_dir = tempfile.mkdtemp()
        self.test_service_path = Path(self.test_dir) / "mmrelay.service"

    def tearDown(self):
        """Clean up test environment."""
        # Clean up temporary files
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('shutil.which')
    def test_get_executable_path_found(self, mock_which):
        """Test getting executable path when mmrelay is found in PATH."""
        mock_which.return_value = "/usr/local/bin/mmrelay"
        
        path = get_executable_path()
        
        self.assertEqual(path, "/usr/local/bin/mmrelay")
        mock_which.assert_called_once_with("mmrelay")

    @patch('shutil.which')
    def test_get_executable_path_not_found(self, mock_which):
        """Test getting executable path when mmrelay is not found in PATH."""
        mock_which.return_value = None
        
        path = get_executable_path()
        
        self.assertEqual(path, sys.executable)

    @patch('mmrelay.setup_utils.Path.home')
    def test_get_user_service_path(self, mock_home):
        """Test getting user service path."""
        mock_home.return_value = Path("/home/user")
        
        service_path = get_user_service_path()
        
        expected_path = Path("/home/user/.config/systemd/user/mmrelay.service")
        self.assertEqual(service_path, expected_path)

    @patch('mmrelay.setup_utils.get_user_service_path')
    def test_service_exists_true(self, mock_get_path):
        """Test service_exists when service file exists."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_get_path.return_value = mock_path
        
        result = service_exists()
        
        self.assertTrue(result)

    @patch('mmrelay.setup_utils.get_user_service_path')
    def test_service_exists_false(self, mock_get_path):
        """Test service_exists when service file doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_get_path.return_value = mock_path
        
        result = service_exists()
        
        self.assertFalse(result)

    @patch('mmrelay.setup_utils.get_user_service_path')
    def test_read_service_file_exists(self, mock_get_path):
        """Test reading service file when it exists."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.read_text.return_value = "service content"
        mock_get_path.return_value = mock_path
        
        content = read_service_file()
        
        self.assertEqual(content, "service content")

    @patch('mmrelay.setup_utils.get_user_service_path')
    def test_read_service_file_not_exists(self, mock_get_path):
        """Test reading service file when it doesn't exist."""
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        mock_get_path.return_value = mock_path
        
        content = read_service_file()
        
        self.assertIsNone(content)

    @patch('os.path.exists')
    def test_get_template_service_path_found(self, mock_exists):
        """Test getting template service path when file is found."""
        # Mock the first path to exist
        mock_exists.side_effect = lambda path: "mmrelay.service" in path
        
        path = get_template_service_path()
        
        self.assertIsNotNone(path)
        self.assertIn("mmrelay.service", path)

    @patch('os.path.exists')
    def test_get_template_service_path_not_found(self, mock_exists):
        """Test getting template service path when file is not found."""
        mock_exists.return_value = False
        
        path = get_template_service_path()
        
        self.assertIsNone(path)

    @patch('mmrelay.setup_utils.get_service_template_path')
    @patch('os.path.exists')
    def test_get_template_service_content_from_file(self, mock_exists, mock_get_template_path):
        """Test getting template service content from file."""
        mock_get_template_path.return_value = "/path/to/template"
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open(read_data="template content")):
            content = get_template_service_content()
        
        self.assertEqual(content, "template content")

    @patch('mmrelay.setup_utils.get_service_template_path')
    @patch('importlib.resources.files')
    def test_get_template_service_content_from_resources(self, mock_files, mock_get_template_path):
        """Test getting template service content from importlib.resources."""
        mock_get_template_path.return_value = None
        
        # Mock importlib.resources
        mock_resource = MagicMock()
        mock_resource.read_text.return_value = "resource content"
        mock_files.return_value.joinpath.return_value = mock_resource
        
        content = get_template_service_content()
        
        self.assertEqual(content, "resource content")

    @patch('mmrelay.setup_utils.get_service_template_path')
    @patch('importlib.resources.files')
    def test_get_template_service_content_fallback(self, mock_files, mock_get_template_path):
        """Test getting template service content with fallback to default."""
        mock_get_template_path.return_value = None
        mock_files.side_effect = FileNotFoundError()
        
        content = get_template_service_content()
        
        # Should return default template
        self.assertIn("[Unit]", content)
        self.assertIn("Description=A Meshtastic <=> Matrix Relay", content)

    @patch('subprocess.run')
    def test_is_service_active_true(self, mock_run):
        """Test is_service_active when service is active."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout.strip.return_value = "active"
        mock_run.return_value = mock_result

        result = is_service_active()

        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["/usr/bin/systemctl", "--user", "is-active", "mmrelay.service"],
            check=False,
            capture_output=True,
            text=True
        )

    @patch('subprocess.run')
    def test_is_service_active_false(self, mock_run):
        """Test is_service_active when service is not active."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = is_service_active()

        self.assertFalse(result)

    @patch('subprocess.run')
    def test_is_service_active_exception(self, mock_run):
        """Test is_service_active when subprocess raises exception."""
        mock_run.side_effect = OSError("Command not found")
        
        result = is_service_active()
        
        self.assertFalse(result)

    @patch('subprocess.run')
    def test_is_service_enabled_true(self, mock_run):
        """Test is_service_enabled when service is enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout.strip.return_value = "enabled"
        mock_run.return_value = mock_result

        result = is_service_enabled()

        self.assertTrue(result)

    @patch('subprocess.run')
    def test_is_service_enabled_false(self, mock_run):
        """Test is_service_enabled when service is not enabled."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result

        result = is_service_enabled()

        self.assertFalse(result)

    @patch('subprocess.run')
    def test_start_service_success(self, mock_run):
        """Test starting service successfully."""
        mock_run.return_value.returncode = 0
        
        result = start_service()
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["/usr/bin/systemctl", "--user", "start", "mmrelay.service"],
            check=True
        )

    @patch('subprocess.run')
    def test_start_service_failure(self, mock_run):
        """Test starting service with failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")
        
        result = start_service()
        
        self.assertFalse(result)

    @patch('subprocess.run')
    def test_reload_daemon_success(self, mock_run):
        """Test reloading daemon successfully."""
        mock_run.return_value.returncode = 0
        
        result = reload_daemon()
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["/usr/bin/systemctl", "--user", "daemon-reload"],
            check=True
        )

    @patch('subprocess.run')
    def test_reload_daemon_failure(self, mock_run):
        """Test reloading daemon with failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")
        
        result = reload_daemon()
        
        self.assertFalse(result)

    @patch('subprocess.run')
    def test_check_lingering_enabled_true(self, mock_run):
        """Test checking lingering when it's enabled."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Linger=yes"
        
        with patch.dict(os.environ, {'USER': 'testuser'}):
            result = check_lingering_enabled()
        
        self.assertTrue(result)

    @patch('subprocess.run')
    def test_check_lingering_enabled_false(self, mock_run):
        """Test checking lingering when it's disabled."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Linger=no"
        
        with patch.dict(os.environ, {'USER': 'testuser'}):
            result = check_lingering_enabled()
        
        self.assertFalse(result)

    @patch('subprocess.run')
    def test_enable_lingering_success(self, mock_run):
        """Test enabling lingering successfully."""
        mock_run.return_value.returncode = 0
        
        with patch.dict(os.environ, {'USER': 'testuser'}):
            result = enable_lingering()
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["sudo", "loginctl", "enable-linger", "testuser"],
            check=False,
            capture_output=True,
            text=True
        )

    @patch('subprocess.run')
    def test_enable_lingering_failure(self, mock_run):
        """Test enabling lingering with failure."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Permission denied"
        
        with patch.dict(os.environ, {'USER': 'testuser'}):
            result = enable_lingering()
        
        self.assertFalse(result)

    @patch('mmrelay.setup_utils.get_executable_path')
    @patch('mmrelay.setup_utils.get_template_service_content')
    @patch('mmrelay.setup_utils.get_user_service_path')
    def test_create_service_file_success(self, mock_get_path, mock_get_content, mock_get_executable):
        """Test creating service file successfully."""
        mock_get_executable.return_value = "/usr/local/bin/mmrelay"
        mock_get_content.return_value = "template content"
        
        mock_path = MagicMock()
        mock_path.parent.mkdir = MagicMock()
        mock_path.write_text = MagicMock()
        mock_get_path.return_value = mock_path
        
        with patch('pathlib.Path') as mock_path_class:
            mock_logs_dir = MagicMock()
            mock_path_class.home.return_value.__truediv__.return_value.__truediv__.return_value = mock_logs_dir
            
            result = create_service_file()
        
        self.assertTrue(result)
        mock_path.write_text.assert_called_once()

    @patch('mmrelay.setup_utils.get_executable_path')
    def test_create_service_file_no_executable(self, mock_get_executable):
        """Test creating service file when executable is not found."""
        mock_get_executable.return_value = None
        
        result = create_service_file()
        
        self.assertFalse(result)

    @patch('mmrelay.setup_utils.read_service_file')
    @patch('mmrelay.setup_utils.get_executable_path')
    def test_service_needs_update_no_existing(self, mock_get_executable, mock_read_service):
        """Test service_needs_update when no existing service file."""
        mock_read_service.return_value = None
        
        needs_update, reason = service_needs_update()
        
        self.assertTrue(needs_update)
        self.assertEqual(reason, "No existing service file found")

    @patch('mmrelay.setup_utils.read_service_file')
    @patch('mmrelay.setup_utils.get_executable_path')
    @patch('mmrelay.setup_utils.get_template_service_path')
    def test_service_needs_update_executable_changed(self, mock_get_template, mock_get_executable, mock_read_service):
        """Test service_needs_update when executable path changed."""
        mock_read_service.return_value = "ExecStart=/old/path/mmrelay"
        mock_get_executable.return_value = "/new/path/mmrelay"
        mock_get_template.return_value = "/path/to/template"
        
        needs_update, reason = service_needs_update()
        
        self.assertTrue(needs_update)
        self.assertIn("does not use the current executable", reason)

    @patch('subprocess.run')
    def test_show_service_status_success(self, mock_run):
        """Test showing service status successfully."""
        mock_run.return_value.stdout = "Service is running"
        
        result = show_service_status()
        
        self.assertTrue(result)
        mock_run.assert_called_once_with(
            ["/usr/bin/systemctl", "--user", "status", "mmrelay.service"],
            check=True,
            capture_output=True,
            text=True
        )

    @patch('subprocess.run')
    def test_show_service_status_failure(self, mock_run):
        """Test showing service status with failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "systemctl")
        
        result = show_service_status()
        
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
