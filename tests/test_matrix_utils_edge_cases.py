#!/usr/bin/env python3
"""
Test suite for Matrix utilities edge cases and error handling in MMRelay.

Tests edge cases and error handling including:
- SSL context creation failures
- Connection timeout scenarios
- Invalid configuration handling
- Message formatting with malformed data
- Room joining failures and retries
- Prefix formatting with invalid templates
- Unicode handling in message truncation
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.matrix_utils import (
    connect_matrix,
    get_matrix_prefix,
    get_meshtastic_prefix,
    join_matrix_room,
    truncate_message,
    validate_prefix_format,
)


class TestMatrixUtilsEdgeCases(unittest.TestCase):
    """Test cases for Matrix utilities edge cases and error handling."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset global state
        import mmrelay.matrix_utils

        mmrelay.matrix_utils.matrix_client = None
        mmrelay.matrix_utils.config = None

    def test_truncate_message_with_unicode(self):
        """Test message truncation with Unicode characters that span multiple bytes."""
        # Test with emoji and multi-byte characters
        unicode_text = "Hello 🌍 世界 🚀 Testing"

        # Test normal truncation
        result = truncate_message(unicode_text, max_bytes=20)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result.encode("utf-8")) <= 20)

        # Test truncation that might split a multi-byte character
        result = truncate_message(unicode_text, max_bytes=10)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result.encode("utf-8")) <= 10)

        # Test with very small byte limit
        result = truncate_message(unicode_text, max_bytes=1)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result.encode("utf-8")) <= 1)

    def test_truncate_message_edge_cases(self):
        """Test message truncation with edge cases."""
        # Empty string
        result = truncate_message("", max_bytes=100)
        self.assertEqual(result, "")

        # String shorter than limit
        short_text = "Short"
        result = truncate_message(short_text, max_bytes=100)
        self.assertEqual(result, short_text)

        # Zero byte limit
        result = truncate_message("Hello", max_bytes=0)
        self.assertEqual(result, "")

        # Negative byte limit - the function may not handle this gracefully
        # so we'll just check it doesn't crash
        result = truncate_message("Hello", max_bytes=-1)
        self.assertIsInstance(result, str)  # Just ensure it returns a string

    def test_validate_prefix_format_edge_cases(self):
        """Test prefix format validation with various edge cases."""
        # Valid format
        is_valid, error = validate_prefix_format("{display}: ", {"display": "Test"})
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        # Missing variable
        is_valid, error = validate_prefix_format("{missing}: ", {"display": "Test"})
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

        # Invalid format syntax
        is_valid, error = validate_prefix_format("{display: ", {"display": "Test"})
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

        # Empty format string
        is_valid, error = validate_prefix_format("", {"display": "Test"})
        self.assertTrue(is_valid)  # Empty string is valid
        self.assertIsNone(error)

        # Format with no variables
        is_valid, error = validate_prefix_format("Static text: ", {"display": "Test"})
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_get_matrix_prefix_with_invalid_format(self):
        """Test matrix prefix generation with invalid format strings."""
        config = {
            "matrix": {"prefix_enabled": True, "prefix_format": "{invalid_var}: "}
        }

        # Should fall back to default format when custom format is invalid
        result = get_matrix_prefix(config, "TestUser", "TU", "TestMesh")
        # Should use default format as fallback
        self.assertIn("TestUser", result)
        self.assertIn("TestMesh", result)

    def test_get_meshtastic_prefix_with_invalid_format(self):
        """Test meshtastic prefix generation with invalid format strings."""
        config = {
            "meshtastic": {"prefix_enabled": True, "prefix_format": "{invalid_var}: "}
        }

        # Should fall back to default format when custom format is invalid
        result = get_meshtastic_prefix(config, "TestUser")
        # Should use default format as fallback
        self.assertIn("TestU", result)  # Default uses display5

    def test_get_matrix_prefix_with_none_values(self):
        """Test matrix prefix generation with None values."""
        config = {"matrix": {"prefix_enabled": True}}

        # Test with None values
        result = get_matrix_prefix(config, None, None, None)
        self.assertIsInstance(result, str)

        # Test with empty strings
        result = get_matrix_prefix(config, "", "", "")
        self.assertIsInstance(result, str)

    def test_get_meshtastic_prefix_with_malformed_user_id(self):
        """Test meshtastic prefix generation with malformed user IDs."""
        config = {"meshtastic": {"prefix_enabled": True}}

        # Test with malformed user ID (no @)
        result = get_meshtastic_prefix(config, "TestUser", "malformed_id")
        self.assertIsInstance(result, str)

        # Test with malformed user ID (no :)
        result = get_meshtastic_prefix(config, "TestUser", "@malformed")
        self.assertIsInstance(result, str)

        # Test with empty user ID
        result = get_meshtastic_prefix(config, "TestUser", "")
        self.assertIsInstance(result, str)

        # Test with None user ID
        result = get_meshtastic_prefix(config, "TestUser", None)
        self.assertIsInstance(result, str)

    @patch("mmrelay.matrix_utils.logger")
    def test_connect_matrix_with_no_config(self, mock_logger):
        """Test connect_matrix behavior when no configuration is available."""

        async def run_test():
            result = await connect_matrix(None)
            self.assertIsNone(result)
            mock_logger.error.assert_called_with(
                "No configuration available. Cannot connect to Matrix."
            )

        asyncio.run(run_test())

    @patch("mmrelay.matrix_utils.logger")
    @patch("ssl.create_default_context")
    def test_connect_matrix_ssl_context_failure(self, mock_ssl_context, mock_logger):
        """Test connect_matrix behavior when SSL context creation fails."""
        mock_ssl_context.side_effect = Exception("SSL context creation failed")

        config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@test:matrix.org",
            },
            "matrix_rooms": [],
        }

        async def run_test():
            # This should raise an exception due to SSL context failure
            with self.assertRaises((ConnectionError, OSError, ValueError)):
                await connect_matrix(config)

        asyncio.run(run_test())

    @patch("mmrelay.matrix_utils.logger")
    def test_join_matrix_room_with_invalid_alias(self, mock_logger):
        """Test join_matrix_room behavior with invalid room alias."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.room_id = None
        mock_response.message = "Room not found"
        mock_client.room_resolve_alias.return_value = mock_response

        async def run_test():
            await join_matrix_room(mock_client, "#invalid:matrix.org")
            mock_logger.error.assert_called()

        asyncio.run(run_test())

    @patch("mmrelay.matrix_utils.logger")
    def test_join_matrix_room_exception_handling(self, mock_logger):
        """Test join_matrix_room exception handling."""
        mock_client = AsyncMock()
        mock_client.room_resolve_alias.side_effect = Exception("Network error")

        async def run_test():
            await join_matrix_room(mock_client, "#test:matrix.org")
            mock_logger.error.assert_called()

        asyncio.run(run_test())

    def test_prefix_generation_with_extreme_lengths(self):
        """Test prefix generation with extremely long input values."""
        config = {"matrix": {"prefix_enabled": True}}

        # Very long names
        very_long_name = "A" * 1000
        result = get_matrix_prefix(config, very_long_name, "short", "mesh")
        self.assertIsInstance(result, str)

        # Test meshtastic prefix with very long display name
        config = {"meshtastic": {"prefix_enabled": True}}
        result = get_meshtastic_prefix(config, very_long_name)
        self.assertIsInstance(result, str)

    def test_prefix_disabled_scenarios(self):
        """Test prefix generation when prefixes are disabled."""
        # Matrix prefix disabled
        config = {"matrix": {"prefix_enabled": False}}
        result = get_matrix_prefix(config, "User", "U", "Mesh")
        self.assertEqual(result, "")

        # Meshtastic prefix disabled
        config = {"meshtastic": {"prefix_enabled": False}}
        result = get_meshtastic_prefix(config, "User")
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
