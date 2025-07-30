import os
import sys
import unittest
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.cli import parse_arguments


class TestCLI(unittest.TestCase):
    def test_parse_arguments_basic(self):
        """Test basic argument parsing functionality."""
        with patch("sys.argv", ["mmrelay"]):
            args = parse_arguments()
            self.assertIsNotNone(args)

    def test_parse_arguments_with_unknown_args(self):
        """Test parse_known_args functionality with unknown arguments."""
        with patch("sys.argv", ["mmrelay", "--unknown-flag", "value"]):
            # Should not raise SystemExit, should handle gracefully
            args = parse_arguments()
            self.assertIsNotNone(args)

    def test_parse_arguments_with_pytest_args(self):
        """Test that pytest arguments are handled gracefully without warnings."""
        with patch("sys.argv", ["mmrelay", "--pytest-arg", "value"]):
            with patch("builtins.print") as mock_print:
                args = parse_arguments()
                self.assertIsNotNone(args)
                # Should not print warning for pytest args
                mock_print.assert_not_called()

    def test_parse_arguments_with_test_args(self):
        """Test that test arguments are handled gracefully without warnings."""
        with patch("sys.argv", ["mmrelay", "--test-flag", "value"]):
            with patch("builtins.print") as mock_print:
                args = parse_arguments()
                self.assertIsNotNone(args)
                # Should not print warning for test args
                mock_print.assert_not_called()

    def test_parse_arguments_with_unknown_non_test_args(self):
        """Test that non-test unknown arguments generate warnings."""
        with patch("sys.argv", ["mmrelay", "--unknown-flag", "value"]):
            with patch("builtins.print") as mock_print:
                args = parse_arguments()
                self.assertIsNotNone(args)
                # Should print warning for non-test unknown args
                mock_print.assert_called_once()
                call_args = mock_print.call_args[0][0]
                self.assertIn("Warning: Unknown arguments ignored", call_args)
                self.assertIn("--unknown-flag", call_args)

    def test_parse_arguments_fallback_to_parse_args(self):
        """Test fallback to parse_args when parse_known_args fails."""
        with patch("sys.argv", ["mmrelay"]):
            with patch("argparse.ArgumentParser.parse_known_args") as mock_parse_known:
                mock_parse_known.side_effect = SystemExit()
                with patch("argparse.ArgumentParser.parse_args") as mock_parse_args:
                    mock_parse_args.return_value = "fallback_args"
                    args = parse_arguments()
                    self.assertEqual(args, "fallback_args")
                    mock_parse_args.assert_called_once()

    def test_parse_arguments_windows_config_handling(self):
        """Test Windows-specific positional config argument handling."""
        with patch("sys.platform", "win32"):
            with patch("sys.argv", ["mmrelay", "config.yaml"]):
                args = parse_arguments()
                # The Windows-specific logic should still work
                self.assertIsNotNone(args)

    def test_parse_arguments_all_flags(self):
        """Test parsing with all supported command line flags."""
        test_args = [
            "mmrelay", "--config", "test.yaml", "--data-dir", "/test", 
            "--log-level", "debug", "--logfile", "test.log",
            "--version", "--generate-config", "--install-service", "--check-config"
        ]
        with patch("sys.argv", test_args):
            args = parse_arguments()
            self.assertIsNotNone(args)


if __name__ == "__main__":
    unittest.main()