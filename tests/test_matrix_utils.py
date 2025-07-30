import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.matrix_utils import (
    _add_truncated_vars,
    _create_mapping_info,
    _get_msgs_to_keep_config,
    bot_command,
    format_reply_message,
    get_interaction_settings,
    get_matrix_prefix,
    get_meshtastic_prefix,
    message_storage_enabled,
    on_room_message,
    strip_quoted_lines,
    truncate_message,
    validate_prefix_format,
)


class TestMatrixUtils(unittest.TestCase):
    def setUp(self):
        """
        Set up common test fixtures for Matrix room message handling tests.
        
        Initializes mocked Matrix room and event objects, and prepares a configuration dictionary for Meshtastic and Matrix settings to be used across test cases.
        """
        self.mock_room = MagicMock()
        self.mock_room.room_id = "!room:matrix.org"
        self.mock_event = MagicMock()
        self.mock_event.sender = "@user:matrix.org"
        self.mock_event.body = "Hello, world!"
        self.mock_event.source = {"content": {"body": "Hello, world!"}}
        self.mock_event.server_timestamp = 1234567890

        self.config = {
            "meshtastic": {
                "broadcast_enabled": True,
                "prefix_enabled": True,
                "prefix_format": "{display5}[M]: ",
                "message_interactions": {"reactions": False, "replies": False},
                "meshnet_name": "test_mesh",
            },
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
            "matrix": {"bot_user_id": "@bot:matrix.org"},
        }

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.bot_start_time", 1234567880)
    @patch("mmrelay.matrix_utils.get_user_display_name", new_callable=AsyncMock)
    @patch("mmrelay.matrix_utils.isinstance")
    def test_on_room_message_simple_text(
        self,
        mock_isinstance,
        mock_get_user_display_name,
        mock_queue_message,
        mock_connect_meshtastic,
    ):
        """
        Test that a simple text message event is correctly processed and queued for Meshtastic relay.
        
        Verifies that when a non-reaction text message is received from a user, the message is queued with the expected content.
        """
        mock_isinstance.return_value = False
        mock_get_user_display_name.return_value = "user"
        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch("mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]):
            # Mock the matrix client
            mock_matrix_client = AsyncMock()
            with patch("mmrelay.matrix_utils.matrix_client", mock_matrix_client):
                # Run the function
                asyncio.run(on_room_message(self.mock_room, self.mock_event))

                # Assert that the message was queued
                mock_queue_message.assert_called_once()
                call_args = mock_queue_message.call_args[1]
                self.assertIn("Hello, world!", call_args["text"])

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.bot_start_time", 1234567880)
    def test_on_room_message_ignore_bot(self, mock_queue_message, mock_connect_meshtastic):
        """
        Test that messages sent by the bot user are ignored and not queued for Meshtastic relay.
        """
        self.mock_event.sender = self.config["matrix"]["bot_user_id"]
        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch("mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]):
            # Mock the matrix client
            mock_matrix_client = AsyncMock()
            with patch("mmrelay.matrix_utils.matrix_client", mock_matrix_client):
                # Run the function
                asyncio.run(on_room_message(self.mock_room, self.mock_event))

                # Assert that the message was not queued
                mock_queue_message.assert_not_called()

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.bot_start_time", 1234567880)
    @patch("mmrelay.matrix_utils.get_message_map_by_matrix_event_id")
    @patch("mmrelay.matrix_utils.get_user_display_name", new_callable=AsyncMock)
    @patch("mmrelay.matrix_utils.isinstance")
    def test_on_room_message_reply_enabled(
        self,
        mock_isinstance,
        mock_get_user_display_name,
        mock_get_message_map,
        mock_queue_message,
        mock_connect_meshtastic,
    ):
        """
        Test that a reply message is correctly processed and queued when reply interactions are enabled.
        
        Ensures that when a Matrix event is a reply and reply interactions are enabled in the configuration, the reply text is extracted and passed to the message queue for Meshtastic relay.
        """
        mock_isinstance.return_value = False
        mock_get_user_display_name.return_value = "user"
        self.config["meshtastic"]["message_interactions"]["replies"] = True
        self.mock_event.source = {
            "content": {
                "m.relates_to": {"m.in_reply_to": {"event_id": "original_event_id"}}
            }
        }
        self.mock_event.body = "> <@original_user:matrix.org> original message\n\nThis is a reply"
        mock_get_message_map.return_value = (
            "meshtastic_id",
            "!room:matrix.org",
            "original_text",
            "test_mesh",
        )

        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch("mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]):
            # Mock the matrix client
            mock_matrix_client = AsyncMock()
            with patch("mmrelay.matrix_utils.matrix_client", mock_matrix_client):
                # Run the function
                asyncio.run(on_room_message(self.mock_room, self.mock_event))

                # Assert that the message was queued
                mock_queue_message.assert_called_once()
                call_args = mock_queue_message.call_args[1]
                self.assertIn("This is a reply", call_args["text"])

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.bot_start_time", 1234567880)
    @patch("mmrelay.matrix_utils.get_user_display_name", new_callable=AsyncMock)
    @patch("mmrelay.matrix_utils.isinstance")
    def test_on_room_message_reply_disabled(
        self,
        mock_isinstance,
        mock_get_user_display_name,
        mock_queue_message,
        mock_connect_meshtastic,
    ):
        """
        Test that a reply message is handled correctly when reply interactions are disabled.
        
        Verifies that when replies are disabled in the configuration, the full event body (including quoted original message) is queued for Meshtastic relay.
        """
        mock_isinstance.return_value = False
        mock_get_user_display_name.return_value = "user"
        self.config["meshtastic"]["message_interactions"]["replies"] = False
        self.mock_event.source = {
            "content": {
                "m.relates_to": {"m.in_reply_to": {"event_id": "original_event_id"}}
            }
        }
        self.mock_event.body = "> <@original_user:matrix.org> original message\n\nThis is a reply"

        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch("mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]):
            # Mock the matrix client
            mock_matrix_client = AsyncMock()
            with patch("mmrelay.matrix_utils.matrix_client", mock_matrix_client):
                # Run the function
                asyncio.run(on_room_message(self.mock_room, self.mock_event))

                # Assert that the message was queued
                mock_queue_message.assert_called_once()
                call_args = mock_queue_message.call_args[1]
                self.assertIn(self.mock_event.body, call_args["text"])

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.bot_start_time", 1234567880)
    @patch("mmrelay.matrix_utils.get_message_map_by_matrix_event_id")
    @patch("mmrelay.matrix_utils.get_user_display_name", new_callable=AsyncMock)
    @patch("mmrelay.matrix_utils.isinstance")
    def test_on_room_message_reaction_enabled(
        self,
        mock_isinstance,
        mock_get_user_display_name,
        mock_get_message_map,
        mock_queue_message,
        mock_connect_meshtastic,
    ):
        # This is a reaction event
        """
        Test that a reaction event is processed and queued when reaction interactions are enabled.
        
        Verifies that when a Matrix reaction event occurs and reaction interactions are enabled in the configuration, the corresponding reaction message is correctly queued for Meshtastic relay with the appropriate text.
        """
        from nio import ReactionEvent

        mock_isinstance.side_effect = lambda event, event_type: event_type == ReactionEvent

        self.config["meshtastic"]["message_interactions"]["reactions"] = True
        self.mock_event.source = {
            "content": {
                "m.relates_to": {
                    "event_id": "original_event_id",
                    "key": "👍",
                    "rel_type": "m.annotation",
                }
            }
        }
        mock_get_message_map.return_value = (
            "meshtastic_id",
            "!room:matrix.org",
            "original_text",
            "test_mesh",
        )
        mock_get_user_display_name.return_value = "user"

        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch("mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]):
            # Mock the matrix client
            mock_matrix_client = AsyncMock()
            with patch("mmrelay.matrix_utils.matrix_client", mock_matrix_client):
                # Run the function
                asyncio.run(on_room_message(self.mock_room, self.mock_event))

                # Assert that the message was queued
                mock_queue_message.assert_called_once()
                call_args = mock_queue_message.call_args[1]
                self.assertIn("reacted 👍 to", call_args["text"])

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.bot_start_time", 1234567880)
    @patch("mmrelay.matrix_utils.isinstance")
    def test_on_room_message_reaction_disabled(
        self, mock_isinstance, mock_queue_message, mock_connect_meshtastic
    ):
        # This is a reaction event
        """
        Test that reaction events are ignored when reaction interactions are disabled in the configuration.
        """
        from nio import ReactionEvent

        mock_isinstance.side_effect = lambda event, event_type: event_type == ReactionEvent

        self.config["meshtastic"]["message_interactions"]["reactions"] = False
        self.mock_event.source = {
            "content": {
                "m.relates_to": {
                    "event_id": "original_event_id",
                    "key": "👍",
                    "rel_type": "m.annotation",
                }
            }
        }

        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch("mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]):
            # Mock the matrix client
            mock_matrix_client = AsyncMock()
            with patch("mmrelay.matrix_utils.matrix_client", mock_matrix_client):
                # Run the function
                asyncio.run(on_room_message(self.mock_room, self.mock_event))

                # Assert that the message was not queued
                mock_queue_message.assert_not_called()

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.bot_start_time", 1234567880)
    def test_on_room_message_unsupported_room(
        self, mock_queue_message, mock_connect_meshtastic
    ):
        """
        Test that messages from unsupported Matrix rooms are ignored by on_room_message.
        
        Verifies that when a message event originates from a room not listed in the configured matrix rooms, the message is not queued for Meshtastic relay.
        """
        self.mock_room.room_id = "!unsupported:matrix.org"
        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch("mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]):
            # Mock the matrix client
            mock_matrix_client = AsyncMock()
            with patch("mmrelay.matrix_utils.matrix_client", mock_matrix_client):
                # Run the function
                asyncio.run(on_room_message(self.mock_room, self.mock_event))

                # Assert that the message was not queued
                mock_queue_message.assert_not_called()


class TestUtilityFunctions(unittest.TestCase):
    """Test cases for Matrix utility functions."""

    def test_get_msgs_to_keep_config_default(self):
        """Test default message retention configuration."""
        import mmrelay.matrix_utils
        original_config = mmrelay.matrix_utils.config
        try:
            mmrelay.matrix_utils.config = {}
            result = _get_msgs_to_keep_config()
            self.assertEqual(result, 500)
        finally:
            mmrelay.matrix_utils.config = original_config

    def test_get_msgs_to_keep_config_legacy(self):
        """Test legacy message retention configuration."""
        import mmrelay.matrix_utils
        original_config = mmrelay.matrix_utils.config
        try:
            mmrelay.matrix_utils.config = {"db": {"msg_map": {"msgs_to_keep": 100}}}
            result = _get_msgs_to_keep_config()
            self.assertEqual(result, 100)
        finally:
            mmrelay.matrix_utils.config = original_config

    def test_get_msgs_to_keep_config_new_format(self):
        """Test new message retention configuration format."""
        import mmrelay.matrix_utils
        original_config = mmrelay.matrix_utils.config
        try:
            mmrelay.matrix_utils.config = {"database": {"msg_map": {"msgs_to_keep": 200}}}
            result = _get_msgs_to_keep_config()
            self.assertEqual(result, 200)
        finally:
            mmrelay.matrix_utils.config = original_config

    def test_create_mapping_info(self):
        """Test creation of message mapping information."""
        result = _create_mapping_info(
            matrix_event_id="$event123",
            room_id="!room:matrix.org",
            text="Hello world",
            meshnet="test_mesh",
            msgs_to_keep=100
        )

        expected = {
            "matrix_event_id": "$event123",
            "room_id": "!room:matrix.org",
            "text": "Hello world",
            "meshnet": "test_mesh",
            "msgs_to_keep": 100
        }
        self.assertEqual(result, expected)

    def test_create_mapping_info_defaults(self):
        """Test creation of mapping info with default values."""
        with patch('mmrelay.matrix_utils._get_msgs_to_keep_config', return_value=500):
            result = _create_mapping_info(
                matrix_event_id="$event123",
                room_id="!room:matrix.org",
                text="Hello world"
            )

            self.assertEqual(result["msgs_to_keep"], 500)
            self.assertIsNone(result["meshnet"])

    def test_get_interaction_settings_new_format(self):
        """Test interaction settings with new configuration format."""
        config = {
            "meshtastic": {
                "message_interactions": {
                    "reactions": True,
                    "replies": False
                }
            }
        }

        result = get_interaction_settings(config)
        expected = {"reactions": True, "replies": False}
        self.assertEqual(result, expected)

    def test_get_interaction_settings_legacy_format(self):
        """Test interaction settings with legacy configuration format."""
        config = {
            "meshtastic": {
                "relay_reactions": True
            }
        }

        result = get_interaction_settings(config)
        expected = {"reactions": True, "replies": False}
        self.assertEqual(result, expected)

    def test_get_interaction_settings_defaults(self):
        """Test interaction settings with no configuration."""
        config = {}

        result = get_interaction_settings(config)
        expected = {"reactions": False, "replies": False}
        self.assertEqual(result, expected)

    def test_message_storage_enabled_true(self):
        """Test message storage enabled when interactions are enabled."""
        interactions = {"reactions": True, "replies": False}
        self.assertTrue(message_storage_enabled(interactions))

        interactions = {"reactions": False, "replies": True}
        self.assertTrue(message_storage_enabled(interactions))

        interactions = {"reactions": True, "replies": True}
        self.assertTrue(message_storage_enabled(interactions))

    def test_message_storage_enabled_false(self):
        """Test message storage disabled when no interactions are enabled."""
        interactions = {"reactions": False, "replies": False}
        self.assertFalse(message_storage_enabled(interactions))

    def test_add_truncated_vars(self):
        """Test addition of truncated variables to format dictionary."""
        format_vars = {}
        _add_truncated_vars(format_vars, "display", "Hello World")

        # Check that truncated variables are added
        self.assertEqual(format_vars["display1"], "H")
        self.assertEqual(format_vars["display5"], "Hello")
        self.assertEqual(format_vars["display10"], "Hello Worl")
        self.assertEqual(format_vars["display20"], "Hello World")

    def test_add_truncated_vars_empty_text(self):
        """Test truncated variables with empty text."""
        format_vars = {}
        _add_truncated_vars(format_vars, "display", "")

        # Should handle empty text gracefully
        self.assertEqual(format_vars["display1"], "")
        self.assertEqual(format_vars["display5"], "")

    def test_add_truncated_vars_none_text(self):
        """Test truncated variables with None text."""
        format_vars = {}
        _add_truncated_vars(format_vars, "display", None)

        # Should convert None to empty string
        self.assertEqual(format_vars["display1"], "")
        self.assertEqual(format_vars["display5"], "")


class TestPrefixFormatting(unittest.TestCase):
    """Test cases for prefix formatting functions."""

    def test_validate_prefix_format_valid(self):
        """Test validation of valid prefix format."""
        format_string = "{display5}[M]: "
        available_vars = {"display5": "Alice"}

        is_valid, error = validate_prefix_format(format_string, available_vars)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_prefix_format_invalid_key(self):
        """Test validation of invalid prefix format with missing key."""
        format_string = "{invalid_key}: "
        available_vars = {"display5": "Alice"}

        is_valid, error = validate_prefix_format(format_string, available_vars)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_get_meshtastic_prefix_enabled(self):
        """Test Meshtastic prefix generation when enabled."""
        config = {
            "meshtastic": {
                "prefix_enabled": True,
                "prefix_format": "{display5}[M]: "
            }
        }

        result = get_meshtastic_prefix(config, "Alice", "@alice:matrix.org")
        self.assertEqual(result, "Alice[M]: ")

    def test_get_meshtastic_prefix_disabled(self):
        """Test Meshtastic prefix generation when disabled."""
        config = {
            "meshtastic": {
                "prefix_enabled": False
            }
        }

        result = get_meshtastic_prefix(config, "Alice")
        self.assertEqual(result, "")

    def test_get_meshtastic_prefix_custom_format(self):
        """Test Meshtastic prefix with custom format."""
        config = {
            "meshtastic": {
                "prefix_enabled": True,
                "prefix_format": "[{display3}]: "
            }
        }

        result = get_meshtastic_prefix(config, "Alice")
        self.assertEqual(result, "[Ali]: ")

    def test_get_meshtastic_prefix_invalid_format(self):
        """Test Meshtastic prefix with invalid format falls back to default."""
        config = {
            "meshtastic": {
                "prefix_enabled": True,
                "prefix_format": "{invalid_var}: "
            }
        }

        result = get_meshtastic_prefix(config, "Alice")
        self.assertEqual(result, "Alice[M]: ")  # Default format

    def test_get_matrix_prefix_enabled(self):
        """Test Matrix prefix generation when enabled."""
        config = {
            "matrix": {
                "prefix_enabled": True,
                "prefix_format": "[{long3}/{mesh}]: "
            }
        }

        result = get_matrix_prefix(config, "Alice", "A", "TestMesh")
        self.assertEqual(result, "[Ali/TestMesh]: ")

    def test_get_matrix_prefix_disabled(self):
        """Test Matrix prefix generation when disabled."""
        config = {
            "matrix": {
                "prefix_enabled": False
            }
        }

        result = get_matrix_prefix(config, "Alice", "A", "TestMesh")
        self.assertEqual(result, "")

    def test_get_matrix_prefix_default_format(self):
        """Test Matrix prefix with default format."""
        config = {
            "matrix": {
                "prefix_enabled": True
                # No custom format specified
            }
        }

        result = get_matrix_prefix(config, "Alice", "A", "TestMesh")
        self.assertEqual(result, "[Alice/TestMesh]: ")  # Default format


class TestTextProcessing(unittest.TestCase):
    """Test cases for text processing functions."""

    def test_truncate_message_under_limit(self):
        """Test message truncation when under byte limit."""
        text = "Hello world"
        result = truncate_message(text, max_bytes=50)
        self.assertEqual(result, "Hello world")

    def test_truncate_message_over_limit(self):
        """Test message truncation when over byte limit."""
        text = "This is a very long message that exceeds the byte limit"
        result = truncate_message(text, max_bytes=20)
        self.assertTrue(len(result.encode('utf-8')) <= 20)
        self.assertTrue(result.startswith("This is"))

    def test_truncate_message_unicode(self):
        """Test message truncation with Unicode characters."""
        text = "Hello 🌍 world"
        result = truncate_message(text, max_bytes=10)
        # Should handle Unicode properly without breaking characters
        self.assertTrue(len(result.encode('utf-8')) <= 10)

    def test_strip_quoted_lines_with_quotes(self):
        """Test stripping quoted lines from text."""
        text = "This is a reply\n> Original message\n> Another quoted line\nNew content"
        result = strip_quoted_lines(text)
        expected = "This is a reply New content"  # Joined with spaces
        self.assertEqual(result, expected)

    def test_strip_quoted_lines_no_quotes(self):
        """Test stripping quoted lines when no quotes exist."""
        text = "This is a normal message\nWith multiple lines"
        result = strip_quoted_lines(text)
        expected = "This is a normal message With multiple lines"  # Joined with spaces
        self.assertEqual(result, expected)

    def test_strip_quoted_lines_only_quotes(self):
        """Test stripping quoted lines when all lines are quoted."""
        text = "> First quoted line\n> Second quoted line"
        result = strip_quoted_lines(text)
        self.assertEqual(result, "")

    def test_format_reply_message(self):
        """Test formatting of reply messages."""
        config = {}  # Using defaults
        result = format_reply_message(config, "Alice Smith", "This is a reply\n> Original message")

        # Should include truncated display name and strip quoted lines
        self.assertTrue(result.startswith("Alice[M]: "))
        self.assertNotIn("> Original message", result)
        self.assertIn("This is a reply", result)


class TestBotCommand(unittest.TestCase):
    """Test cases for bot command detection."""

    @patch('mmrelay.matrix_utils.bot_user_id', '@bot:matrix.org')
    @patch('mmrelay.matrix_utils.bot_user_name', 'Bot')
    def test_bot_command_direct_mention(self):
        """Test bot command with direct mention."""
        mock_event = MagicMock()
        mock_event.body = "!help"
        mock_event.source = {"content": {"formatted_body": "!help"}}

        result = bot_command("help", mock_event)
        self.assertTrue(result)

    @patch('mmrelay.matrix_utils.bot_user_id', '@bot:matrix.org')
    @patch('mmrelay.matrix_utils.bot_user_name', 'Bot')
    def test_bot_command_no_match(self):
        """Test bot command that doesn't match."""
        mock_event = MagicMock()
        mock_event.body = "regular message"
        mock_event.source = {"content": {"formatted_body": "regular message"}}

        result = bot_command("help", mock_event)
        self.assertFalse(result)

    @patch('mmrelay.matrix_utils.bot_user_id', '@bot:matrix.org')
    @patch('mmrelay.matrix_utils.bot_user_name', 'Bot')
    def test_bot_command_case_insensitive(self):
        """Test bot command case insensitivity."""
        mock_event = MagicMock()
        mock_event.body = "!HELP"
        mock_event.source = {"content": {"formatted_body": "!HELP"}}

        result = bot_command("HELP", mock_event)  # Command should match case
        self.assertTrue(result)

    @patch('mmrelay.matrix_utils.bot_user_id', '@bot:matrix.org')
    @patch('mmrelay.matrix_utils.bot_user_name', 'Bot')
    def test_bot_command_with_args(self):
        """Test bot command with arguments."""
        mock_event = MagicMock()
        mock_event.body = "!help me please"
        mock_event.source = {"content": {"formatted_body": "!help me please"}}

        result = bot_command("help", mock_event)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
