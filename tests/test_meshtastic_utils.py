import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Un-mock meshtastic so we can use real objects
if "meshtastic" in sys.modules:
    del sys.modules["meshtastic"]

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mmrelay.meshtastic_utils import on_meshtastic_message


class TestMeshtasticUtils(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.mock_interface = MagicMock()
        self.mock_interface.myInfo.my_node_num = 12345
        self.mock_packet = {
            "fromId": "!fromId",
            "to": "^all",
            "decoded": {"text": "Hello, world!", "portnum": "TEXT_MESSAGE_APP"},
            "channel": 0,
            "id": "message_id",
        }
        self.config = {
            "meshtastic": {
                "meshnet_name": "test_mesh",
                "message_interactions": {"reactions": False, "replies": False},
            },
            "matrix_rooms": [{"id": "!room:matrix.org", "meshtastic_channel": 0}],
        }

    def tearDown(self):
        self.loop.close()

    @patch("mmrelay.matrix_utils.matrix_relay", new_callable=AsyncMock)
    @patch("mmrelay.meshtastic_utils.get_longname")
    @patch("mmrelay.meshtastic_utils.get_shortname")
    @patch("mmrelay.plugin_loader.load_plugins")
    @patch("mmrelay.matrix_utils.get_interaction_settings")
    @patch("mmrelay.meshtastic_utils.logger")
    def test_on_meshtastic_message_simple_text(
        self,
        mock_logger,
        mock_get_interaction_settings,
        mock_load_plugins,
        mock_get_shortname,
        mock_get_longname,
        mock_matrix_relay,
    ):
        mock_load_plugins.return_value = []
        mock_get_longname.return_value = "longname"
        mock_get_shortname.return_value = "shortname"
        mock_get_interaction_settings.return_value = {
            "reactions": False,
            "replies": False,
        }

        from meshtastic import mesh_interface

        self.mock_packet["to"] = mesh_interface.BROADCAST_NUM

        with patch("mmrelay.meshtastic_utils.config", self.config), patch(
            "mmrelay.meshtastic_utils.event_loop", self.loop
        ), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.config["matrix_rooms"]
        ):
            # Run the function
            on_meshtastic_message(self.mock_packet, self.mock_interface)

            # Assert that the message was relayed
            self.loop.run_until_complete(asyncio.sleep(0.1))
            mock_matrix_relay.assert_called_once()
            call_args = mock_matrix_relay.call_args[0]
            self.assertIn("Hello, world!", call_args["text"])

    @patch("mmrelay.matrix_utils.matrix_relay", new_callable=AsyncMock)
    @patch("mmrelay.meshtastic_utils.logger")
    def test_on_meshtastic_message_unmapped_channel(self, mock_logger, mock_matrix_relay):
        self.mock_packet["channel"] = 1
        with patch("mmrelay.meshtastic_utils.config", self.config), patch(
            "mmrelay.meshtastic_utils.event_loop", self.loop
        ), patch(
            "mmrelay.meshtastic_utils.matrix_rooms", self.config["matrix_rooms"]
        ):
            # Run the function
            on_meshtastic_message(self.mock_packet, self.mock_interface)

            # Assert that the message was not relayed
            self.loop.run_until_complete(asyncio.sleep(0.1))
            mock_matrix_relay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
