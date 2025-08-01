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
    connect_matrix,
    format_reply_message,
    get_interaction_settings,
    get_matrix_prefix,
    get_meshtastic_prefix,
    get_user_display_name,
    join_matrix_room,
    matrix_relay,
    message_storage_enabled,
    on_room_message,
    send_reply_to_meshtastic,
    strip_quoted_lines,
    truncate_message,
    upload_image,
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
        ), patch(
            "mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]
        ):
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
    def test_on_room_message_ignore_bot(
        self, mock_queue_message, mock_connect_meshtastic
    ):
        """
        Test that messages sent by the bot user are ignored and not queued for Meshtastic relay.
        """
        self.mock_event.sender = self.config["matrix"]["bot_user_id"]
        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch(
            "mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]
        ):
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
        self.mock_event.body = (
            "> <@original_user:matrix.org> original message\n\nThis is a reply"
        )
        mock_get_message_map.return_value = (
            "meshtastic_id",
            "!room:matrix.org",
            "original_text",
            "test_mesh",
        )

        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch(
            "mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]
        ):
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
        self.mock_event.body = (
            "> <@original_user:matrix.org> original message\n\nThis is a reply"
        )

        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch(
            "mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]
        ):
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

        mock_isinstance.side_effect = (
            lambda event, event_type: event_type == ReactionEvent
        )

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
        ), patch(
            "mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]
        ):
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

        mock_isinstance.side_effect = (
            lambda event, event_type: event_type == ReactionEvent
        )

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
        ), patch(
            "mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]
        ):
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
        Test that messages from Matrix rooms not in the configured list are ignored.

        Ensures that when a message event originates from an unsupported Matrix room, it is not queued for Meshtastic relay.
        """
        self.mock_room.room_id = "!unsupported:matrix.org"
        with patch("mmrelay.matrix_utils.config", self.config), patch(
            "mmrelay.matrix_utils.matrix_rooms", self.config["matrix_rooms"]
        ), patch(
            "mmrelay.matrix_utils.bot_user_id", self.config["matrix"]["bot_user_id"]
        ):
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
        """
        Test that the default message retention value is returned when no configuration is set.
        """
        import mmrelay.matrix_utils

        original_config = mmrelay.matrix_utils.config
        try:
            mmrelay.matrix_utils.config = {}
            result = _get_msgs_to_keep_config()
            self.assertEqual(result, 500)
        finally:
            mmrelay.matrix_utils.config = original_config

    def test_get_msgs_to_keep_config_legacy(self):
        """
        Test that the legacy configuration format correctly sets the message retention value.
        """
        import mmrelay.matrix_utils

        original_config = mmrelay.matrix_utils.config
        try:
            mmrelay.matrix_utils.config = {"db": {"msg_map": {"msgs_to_keep": 100}}}
            result = _get_msgs_to_keep_config()
            self.assertEqual(result, 100)
        finally:
            mmrelay.matrix_utils.config = original_config

    def test_get_msgs_to_keep_config_new_format(self):
        """
        Test that the new configuration format correctly sets the message retention value.

        Verifies that `_get_msgs_to_keep_config()` returns the expected value when the configuration uses the new nested format for message retention.
        """
        import mmrelay.matrix_utils

        original_config = mmrelay.matrix_utils.config
        try:
            mmrelay.matrix_utils.config = {
                "database": {"msg_map": {"msgs_to_keep": 200}}
            }
            result = _get_msgs_to_keep_config()
            self.assertEqual(result, 200)
        finally:
            mmrelay.matrix_utils.config = original_config

    def test_create_mapping_info(self):
        """
        Tests that _create_mapping_info returns a dictionary with the correct message mapping information based on the provided parameters.
        """
        result = _create_mapping_info(
            matrix_event_id="$event123",
            room_id="!room:matrix.org",
            text="Hello world",
            meshnet="test_mesh",
            msgs_to_keep=100,
        )

        expected = {
            "matrix_event_id": "$event123",
            "room_id": "!room:matrix.org",
            "text": "Hello world",
            "meshnet": "test_mesh",
            "msgs_to_keep": 100,
        }
        self.assertEqual(result, expected)

    def test_create_mapping_info_defaults(self):
        """
        Test that _create_mapping_info returns a mapping dictionary with default values when optional parameters are not provided.
        """
        with patch("mmrelay.matrix_utils._get_msgs_to_keep_config", return_value=500):
            result = _create_mapping_info(
                matrix_event_id="$event123",
                room_id="!room:matrix.org",
                text="Hello world",
            )

            self.assertEqual(result["msgs_to_keep"], 500)
            self.assertIsNone(result["meshnet"])

    def test_get_interaction_settings_new_format(self):
        """
        Tests that interaction settings are correctly retrieved from a configuration using the new format.
        """
        config = {
            "meshtastic": {
                "message_interactions": {"reactions": True, "replies": False}
            }
        }

        result = get_interaction_settings(config)
        expected = {"reactions": True, "replies": False}
        self.assertEqual(result, expected)

    def test_get_interaction_settings_legacy_format(self):
        """
        Test that interaction settings are correctly parsed from a legacy configuration format.

        Verifies that the function returns the expected dictionary when only legacy keys are present in the configuration.
        """
        config = {"meshtastic": {"relay_reactions": True}}

        result = get_interaction_settings(config)
        expected = {"reactions": True, "replies": False}
        self.assertEqual(result, expected)

    def test_get_interaction_settings_defaults(self):
        """
        Test that default interaction settings are returned as disabled when no configuration is provided.
        """
        config = {}

        result = get_interaction_settings(config)
        expected = {"reactions": False, "replies": False}
        self.assertEqual(result, expected)

    def test_message_storage_enabled_true(self):
        """
        Test that message storage is enabled when either reactions or replies are enabled in the interaction settings.
        """
        interactions = {"reactions": True, "replies": False}
        self.assertTrue(message_storage_enabled(interactions))

        interactions = {"reactions": False, "replies": True}
        self.assertTrue(message_storage_enabled(interactions))

        interactions = {"reactions": True, "replies": True}
        self.assertTrue(message_storage_enabled(interactions))

    def test_message_storage_enabled_false(self):
        """
        Test that message storage is disabled when both reactions and replies are disabled in the interaction settings.
        """
        interactions = {"reactions": False, "replies": False}
        self.assertFalse(message_storage_enabled(interactions))

    def test_add_truncated_vars(self):
        """
        Tests that truncated versions of a string are correctly added to a format dictionary with specific key suffixes.
        """
        format_vars = {}
        _add_truncated_vars(format_vars, "display", "Hello World")

        # Check that truncated variables are added
        self.assertEqual(format_vars["display1"], "H")
        self.assertEqual(format_vars["display5"], "Hello")
        self.assertEqual(format_vars["display10"], "Hello Worl")
        self.assertEqual(format_vars["display20"], "Hello World")

    def test_add_truncated_vars_empty_text(self):
        """
        Test that _add_truncated_vars correctly handles empty string input by setting truncated variables to empty strings.
        """
        format_vars = {}
        _add_truncated_vars(format_vars, "display", "")

        # Should handle empty text gracefully
        self.assertEqual(format_vars["display1"], "")
        self.assertEqual(format_vars["display5"], "")

    def test_add_truncated_vars_none_text(self):
        """
        Test that truncated variable keys are added with empty string values when the input text is None.
        """
        format_vars = {}
        _add_truncated_vars(format_vars, "display", None)

        # Should convert None to empty string
        self.assertEqual(format_vars["display1"], "")
        self.assertEqual(format_vars["display5"], "")


class TestPrefixFormatting(unittest.TestCase):
    """Test cases for prefix formatting functions."""

    def test_validate_prefix_format_valid(self):
        """
        Tests that a valid prefix format string with available variables passes validation without errors.
        """
        format_string = "{display5}[M]: "
        available_vars = {"display5": "Alice"}

        is_valid, error = validate_prefix_format(format_string, available_vars)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_prefix_format_invalid_key(self):
        """
        Tests that validate_prefix_format correctly identifies an invalid prefix format string containing a missing key.

        Verifies that the function returns False and provides an error message when the format string references a key not present in the available variables.
        """
        format_string = "{invalid_key}: "
        available_vars = {"display5": "Alice"}

        is_valid, error = validate_prefix_format(format_string, available_vars)
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_get_meshtastic_prefix_enabled(self):
        """
        Tests that the Meshtastic prefix is generated using the specified format when prefixing is enabled in the configuration.
        """
        config = {
            "meshtastic": {"prefix_enabled": True, "prefix_format": "{display5}[M]: "}
        }

        result = get_meshtastic_prefix(config, "Alice", "@alice:matrix.org")
        self.assertEqual(result, "Alice[M]: ")

    def test_get_meshtastic_prefix_disabled(self):
        """
        Tests that no Meshtastic prefix is generated when prefixing is disabled in the configuration.
        """
        config = {"meshtastic": {"prefix_enabled": False}}

        result = get_meshtastic_prefix(config, "Alice")
        self.assertEqual(result, "")

    def test_get_meshtastic_prefix_custom_format(self):
        """
        Tests that a custom Meshtastic prefix format is applied correctly using the truncated display name.
        """
        config = {
            "meshtastic": {"prefix_enabled": True, "prefix_format": "[{display3}]: "}
        }

        result = get_meshtastic_prefix(config, "Alice")
        self.assertEqual(result, "[Ali]: ")

    def test_get_meshtastic_prefix_invalid_format(self):
        """
        Test that get_meshtastic_prefix falls back to the default format when given an invalid prefix format string.
        """
        config = {
            "meshtastic": {"prefix_enabled": True, "prefix_format": "{invalid_var}: "}
        }

        result = get_meshtastic_prefix(config, "Alice")
        self.assertEqual(result, "Alice[M]: ")  # Default format

    def test_get_matrix_prefix_enabled(self):
        """
        Tests that the Matrix prefix is generated correctly when prefixing is enabled and a custom format is provided.
        """
        config = {
            "matrix": {"prefix_enabled": True, "prefix_format": "[{long3}/{mesh}]: "}
        }

        result = get_matrix_prefix(config, "Alice", "A", "TestMesh")
        self.assertEqual(result, "[Ali/TestMesh]: ")

    def test_get_matrix_prefix_disabled(self):
        """
        Test that no Matrix prefix is generated when prefixing is disabled in the configuration.
        """
        config = {"matrix": {"prefix_enabled": False}}

        result = get_matrix_prefix(config, "Alice", "A", "TestMesh")
        self.assertEqual(result, "")

    def test_get_matrix_prefix_default_format(self):
        """
        Tests that the default Matrix prefix format is used when no custom format is specified in the configuration.
        """
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
        """
        Tests that a message shorter than the specified byte limit is not truncated by the truncate_message function.
        """
        text = "Hello world"
        result = truncate_message(text, max_bytes=50)
        self.assertEqual(result, "Hello world")

    def test_truncate_message_over_limit(self):
        """
        Test that messages exceeding the specified byte limit are truncated without breaking character encoding.
        """
        text = "This is a very long message that exceeds the byte limit"
        result = truncate_message(text, max_bytes=20)
        self.assertTrue(len(result.encode("utf-8")) <= 20)
        self.assertTrue(result.startswith("This is"))

    def test_truncate_message_unicode(self):
        """
        Tests that truncating a message containing Unicode characters does not split characters and respects the byte limit.
        """
        text = "Hello 🌍 world"
        result = truncate_message(text, max_bytes=10)
        # Should handle Unicode properly without breaking characters
        self.assertTrue(len(result.encode("utf-8")) <= 10)

    def test_strip_quoted_lines_with_quotes(self):
        """
        Tests that quoted lines (starting with '>') are removed from multi-line text, and remaining lines are joined with spaces.
        """
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
        """
        Tests that stripping quoted lines from text returns an empty string when all lines are quoted.
        """
        text = "> First quoted line\n> Second quoted line"
        result = strip_quoted_lines(text)
        self.assertEqual(result, "")

    def test_format_reply_message(self):
        """
        Tests that reply messages are formatted with a truncated display name and quoted lines are removed from the message body.
        """
        config = {}  # Using defaults
        result = format_reply_message(
            config, "Alice Smith", "This is a reply\n> Original message"
        )

        # Should include truncated display name and strip quoted lines
        self.assertTrue(result.startswith("Alice[M]: "))
        self.assertNotIn("> Original message", result)
        self.assertIn("This is a reply", result)


class TestBotCommand(unittest.TestCase):
    """Test cases for bot command detection."""

    @patch("mmrelay.matrix_utils.bot_user_id", "@bot:matrix.org")
    @patch("mmrelay.matrix_utils.bot_user_name", "Bot")
    def test_bot_command_direct_mention(self):
        """
        Tests that a message starting with the bot command triggers correct command detection.
        """
        mock_event = MagicMock()
        mock_event.body = "!help"
        mock_event.source = {"content": {"formatted_body": "!help"}}

        result = bot_command("help", mock_event)
        self.assertTrue(result)

    @patch("mmrelay.matrix_utils.bot_user_id", "@bot:matrix.org")
    @patch("mmrelay.matrix_utils.bot_user_name", "Bot")
    def test_bot_command_no_match(self):
        """
        Test that a non-command message does not trigger bot command detection.
        """
        mock_event = MagicMock()
        mock_event.body = "regular message"
        mock_event.source = {"content": {"formatted_body": "regular message"}}

        result = bot_command("help", mock_event)
        self.assertFalse(result)

    @patch("mmrelay.matrix_utils.bot_user_id", "@bot:matrix.org")
    @patch("mmrelay.matrix_utils.bot_user_name", "Bot")
    def test_bot_command_case_insensitive(self):
        """
        Test that bot command detection is case-insensitive by verifying a command matches regardless of letter case.
        """
        mock_event = MagicMock()
        mock_event.body = "!HELP"
        mock_event.source = {"content": {"formatted_body": "!HELP"}}

        result = bot_command("HELP", mock_event)  # Command should match case
        self.assertTrue(result)

    @patch("mmrelay.matrix_utils.bot_user_id", "@bot:matrix.org")
    @patch("mmrelay.matrix_utils.bot_user_name", "Bot")
    def test_bot_command_with_args(self):
        """
        Test that the bot command is correctly detected when followed by additional arguments.
        """
        mock_event = MagicMock()
        mock_event.body = "!help me please"
        mock_event.source = {"content": {"formatted_body": "!help me please"}}

        result = bot_command("help", mock_event)
        self.assertTrue(result)


class TestAsyncMatrixFunctions(unittest.TestCase):
    """Test cases for async Matrix functions."""

    def setUp(self):
        """Set up test fixtures for async function tests."""
        self.config = {
            "matrix": {
                "homeserver": "https://matrix.org",
                "access_token": "test_token",
                "bot_user_id": "@bot:matrix.org",
                "prefix_enabled": True,
            },
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
        }

    @patch("mmrelay.matrix_utils.AsyncClient")
    @patch("mmrelay.matrix_utils.logger")
    async def test_connect_matrix_success(self, mock_logger, mock_async_client):
        """Test successful Matrix connection."""
        # Mock the AsyncClient instance
        mock_client_instance = AsyncMock()
        mock_async_client.return_value = mock_client_instance

        # Mock whoami response
        mock_whoami_response = MagicMock()
        mock_whoami_response.device_id = "test_device_id"
        mock_client_instance.whoami.return_value = mock_whoami_response

        # Mock get_displayname response
        mock_displayname_response = MagicMock()
        mock_displayname_response.displayname = "Test Bot"
        mock_client_instance.get_displayname.return_value = mock_displayname_response

        result = await connect_matrix(self.config)

        # Verify client was created and configured
        mock_async_client.assert_called_once()
        self.assertEqual(result, mock_client_instance)
        mock_client_instance.whoami.assert_called_once()

    @patch("mmrelay.matrix_utils.AsyncClient")
    @patch("mmrelay.matrix_utils.logger")
    async def test_connect_matrix_whoami_error(self, mock_logger, mock_async_client):
        """Test Matrix connection when whoami fails."""
        from nio import WhoamiError

        mock_client_instance = AsyncMock()
        mock_async_client.return_value = mock_client_instance

        # Mock whoami error
        mock_whoami_error = WhoamiError("Authentication failed")
        mock_client_instance.whoami.return_value = mock_whoami_error

        result = await connect_matrix(self.config)

        # Should still return client but with None device_id
        self.assertEqual(result, mock_client_instance)
        self.assertIsNone(mock_client_instance.device_id)

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.logger")
    async def test_join_matrix_room_by_id(self, mock_logger, mock_matrix_client):
        """Test joining a Matrix room by room ID."""
        mock_matrix_client.join.return_value = AsyncMock()

        await join_matrix_room(mock_matrix_client, "!room:matrix.org")

        mock_matrix_client.join.assert_called_once_with("!room:matrix.org")

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.matrix_rooms", [])
    @patch("mmrelay.matrix_utils.logger")
    async def test_join_matrix_room_by_alias(self, mock_logger, mock_matrix_client):
        """Test joining a Matrix room by room alias."""
        # Mock room alias resolution
        mock_resolve_response = MagicMock()
        mock_resolve_response.room_id = "!resolved:matrix.org"
        mock_matrix_client.room_resolve_alias.return_value = mock_resolve_response
        mock_matrix_client.join.return_value = AsyncMock()

        await join_matrix_room(mock_matrix_client, "#room:matrix.org")

        mock_matrix_client.room_resolve_alias.assert_called_once_with("#room:matrix.org")
        mock_matrix_client.join.assert_called_once_with("!resolved:matrix.org")

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.logger")
    async def test_join_matrix_room_alias_resolution_fails(self, mock_logger, mock_matrix_client):
        """Test joining a Matrix room when alias resolution fails."""
        # Mock failed alias resolution
        mock_resolve_response = MagicMock()
        mock_resolve_response.room_id = None
        mock_matrix_client.room_resolve_alias.return_value = mock_resolve_response

        await join_matrix_room(mock_matrix_client, "#room:matrix.org")

        # Should not attempt to join if resolution fails
        mock_matrix_client.join.assert_not_called()

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.get_interaction_settings")
    @patch("mmrelay.matrix_utils.message_storage_enabled")
    @patch("mmrelay.matrix_utils.store_message_map")
    @patch("mmrelay.matrix_utils.prune_message_map")
    @patch("mmrelay.matrix_utils.logger")
    async def test_matrix_relay_simple_message(self, mock_logger, mock_prune, mock_store,
                                               mock_storage_enabled, mock_get_interactions,
                                               mock_matrix_client):
        """Test relaying a simple message to Matrix."""
        # Setup mocks
        mock_get_interactions.return_value = {"reactions": False, "replies": False}
        mock_storage_enabled.return_value = False

        # Mock successful message send
        mock_response = MagicMock()
        mock_response.event_id = "$event123"
        mock_matrix_client.room_send.return_value = mock_response

        await matrix_relay(
            room_id="!room:matrix.org",
            message="Hello world",
            longname="Alice",
            shortname="A",
            meshnet_name="TestMesh",
            portnum=1,
        )

        # Verify message was sent
        mock_matrix_client.room_send.assert_called_once()
        call_args = mock_matrix_client.room_send.call_args
        self.assertEqual(call_args[1]["room_id"], "!room:matrix.org")
        self.assertEqual(call_args[1]["message_type"], "m.room.message")

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.get_interaction_settings")
    @patch("mmrelay.matrix_utils.message_storage_enabled")
    @patch("mmrelay.matrix_utils.logger")
    async def test_matrix_relay_emote_message(self, mock_logger, mock_storage_enabled,
                                              mock_get_interactions, mock_matrix_client):
        """Test relaying an emote message to Matrix."""
        mock_get_interactions.return_value = {"reactions": False, "replies": False}
        mock_storage_enabled.return_value = False

        mock_response = MagicMock()
        mock_response.event_id = "$event123"
        mock_matrix_client.room_send.return_value = mock_response

        await matrix_relay(
            room_id="!room:matrix.org",
            message="waves",
            longname="Alice",
            shortname="A",
            meshnet_name="TestMesh",
            portnum=1,
            emote=True,
        )

        # Verify emote message was sent
        mock_matrix_client.room_send.assert_called_once()
        call_args = mock_matrix_client.room_send.call_args
        content = call_args[1]["content"]
        self.assertEqual(content["msgtype"], "m.emote")

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.logger")
    async def test_matrix_relay_client_none(self, mock_logger, mock_matrix_client):
        """Test matrix_relay when matrix_client is None."""
        mock_matrix_client = None

        # Should return early without sending
        await matrix_relay(
            room_id="!room:matrix.org",
            message="Hello world",
            longname="Alice",
            shortname="A",
            meshnet_name="TestMesh",
            portnum=1,
        )

        # Should log error about None client
        mock_logger.error.assert_called()

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.logger")
    async def test_get_user_display_name_room_name(self, mock_logger, mock_matrix_client):
        """Test getting user display name from room."""
        mock_room = MagicMock()
        mock_room.user_name.return_value = "Room Display Name"

        mock_event = MagicMock()
        mock_event.sender = "@user:matrix.org"

        result = await get_user_display_name(mock_room, mock_event)

        self.assertEqual(result, "Room Display Name")
        mock_room.user_name.assert_called_once_with("@user:matrix.org")

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.logger")
    async def test_get_user_display_name_fallback(self, mock_logger, mock_matrix_client):
        """Test getting user display name with fallback to Matrix API."""
        mock_room = MagicMock()
        mock_room.user_name.return_value = None  # No room-specific name

        mock_event = MagicMock()
        mock_event.sender = "@user:matrix.org"

        # Mock Matrix API response
        mock_displayname_response = MagicMock()
        mock_displayname_response.displayname = "Global Display Name"
        mock_matrix_client.get_displayname.return_value = mock_displayname_response

        result = await get_user_display_name(mock_room, mock_event)

        self.assertEqual(result, "Global Display Name")
        mock_matrix_client.get_displayname.assert_called_once_with("@user:matrix.org")

    @patch("mmrelay.matrix_utils.matrix_client")
    @patch("mmrelay.matrix_utils.logger")
    async def test_get_user_display_name_no_displayname(self, mock_logger, mock_matrix_client):
        """Test getting user display name when no display name is set."""
        mock_room = MagicMock()
        mock_room.user_name.return_value = None

        mock_event = MagicMock()
        mock_event.sender = "@user:matrix.org"

        # Mock Matrix API response with no display name
        mock_displayname_response = MagicMock()
        mock_displayname_response.displayname = None
        mock_matrix_client.get_displayname.return_value = mock_displayname_response

        result = await get_user_display_name(mock_room, mock_event)

        # Should fallback to sender ID
        self.assertEqual(result, "@user:matrix.org")

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.logger")
    async def test_send_reply_to_meshtastic_with_reply_id(self, mock_logger, mock_queue, mock_connect):
        """Test sending a reply to Meshtastic with reply_id."""
        mock_room_config = {"meshtastic_channel": 0}
        mock_room = MagicMock()
        mock_event = MagicMock()

        await send_reply_to_meshtastic(
            reply_message="Test reply",
            full_display_name="Alice",
            room_config=mock_room_config,
            room=mock_room,
            event=mock_event,
            text="Original text",
            storage_enabled=True,
            local_meshnet_name="TestMesh",
            reply_id=12345,
        )

        # Should queue message with reply_id
        mock_queue.assert_called_once()
        call_kwargs = mock_queue.call_args[1]
        self.assertEqual(call_kwargs["reply_id"], 12345)

    @patch("mmrelay.matrix_utils.connect_meshtastic")
    @patch("mmrelay.matrix_utils.queue_message")
    @patch("mmrelay.matrix_utils.logger")
    async def test_send_reply_to_meshtastic_no_reply_id(self, mock_logger, mock_queue, mock_connect):
        """Test sending a reply to Meshtastic without reply_id."""
        mock_room_config = {"meshtastic_channel": 0}
        mock_room = MagicMock()
        mock_event = MagicMock()

        await send_reply_to_meshtastic(
            reply_message="Test reply",
            full_display_name="Alice",
            room_config=mock_room_config,
            room=mock_room,
            event=mock_event,
            text="Original text",
            storage_enabled=False,
            local_meshnet_name="TestMesh",
            reply_id=None,
        )

        # Should queue message without reply_id
        mock_queue.assert_called_once()
        call_kwargs = mock_queue.call_args[1]
        self.assertIsNone(call_kwargs.get("reply_id"))


class TestImageUploadFunctions(unittest.TestCase):
    """Test cases for image upload functions."""

    @patch("mmrelay.matrix_utils.io.BytesIO")
    async def test_upload_image(self, mock_bytesio):
        """Test uploading an image to Matrix."""
        from PIL import Image

        # Mock PIL Image
        mock_image = MagicMock(spec=Image.Image)
        mock_buffer = MagicMock()
        mock_bytesio.return_value = mock_buffer
        mock_buffer.getvalue.return_value = b"fake_image_data"

        # Mock Matrix client
        mock_client = AsyncMock()
        mock_upload_response = MagicMock()
        mock_client.upload.return_value = (mock_upload_response, None)

        result = await upload_image(mock_client, mock_image, "test.png")

        # Verify image was saved and uploaded
        mock_image.save.assert_called_once()
        mock_client.upload.assert_called_once()
        self.assertEqual(result, mock_upload_response)

    async def test_send_room_image(self):
        """Test sending an uploaded image to a Matrix room."""
        mock_client = AsyncMock()
        mock_upload_response = MagicMock()
        mock_upload_response.content_uri = "mxc://matrix.org/test123"

        await send_room_image(mock_client, "!room:matrix.org", mock_upload_response)

        # Verify room_send was called with correct parameters
        mock_client.room_send.assert_called_once()
        call_args = mock_client.room_send.call_args
        self.assertEqual(call_args[1]["room_id"], "!room:matrix.org")
        self.assertEqual(call_args[1]["message_type"], "m.room.message")
        content = call_args[1]["content"]
        self.assertEqual(content["msgtype"], "m.image")
        self.assertEqual(content["url"], "mxc://matrix.org/test123")


if __name__ == "__main__":
    unittest.main()
