import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.matrix_utils import on_room_message


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


if __name__ == "__main__":
    unittest.main()
