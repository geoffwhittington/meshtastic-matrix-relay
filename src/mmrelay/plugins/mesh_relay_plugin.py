# Note: This plugin was experimental and is not functional.

import base64
import json
import re

from meshtastic import mesh_pb2

from mmrelay.constants.database import DEFAULT_MAX_DATA_ROWS_PER_NODE_MESH_RELAY
from mmrelay.plugins.base_plugin import BasePlugin, config


class Plugin(BasePlugin):
    """Core mesh-to-Matrix relay plugin.

    Handles bidirectional message relay between Meshtastic mesh network
    and Matrix chat rooms. Processes radio packets and forwards them
    to configured Matrix rooms, and vice versa.

    This plugin is fundamental to the relay's core functionality and
    typically runs with high priority to ensure messages are properly
    bridged between the two networks.

    Configuration:
        max_data_rows_per_node: 50 (reduced storage for performance)
    """

    plugin_name = "mesh_relay"
    max_data_rows_per_node = DEFAULT_MAX_DATA_ROWS_PER_NODE_MESH_RELAY

    def normalize(self, dict_obj):
        """
        Converts packet data in various formats (dict, JSON string, or plain string) into a normalized dictionary with raw data fields removed.

        Parameters:
            dict_obj: Packet data as a dictionary, JSON string, or plain string.

        Returns:
            A dictionary representing the normalized packet with raw fields stripped.
        """
        if not isinstance(dict_obj, dict):
            try:
                dict_obj = json.loads(dict_obj)
            except (json.JSONDecodeError, TypeError):
                dict_obj = {"decoded": {"text": dict_obj}}

        return self.strip_raw(dict_obj)

    def process(self, packet):
        """Process and prepare packet data for relay.

        Args:
            packet: Raw packet data to process

        Returns:
            dict: Processed packet with base64-encoded binary payloads

        Normalizes packet format and encodes binary payloads as base64
        for JSON serialization and Matrix transmission.
        """
        packet = self.normalize(packet)

        if "decoded" in packet and "payload" in packet["decoded"]:
            if isinstance(packet["decoded"]["payload"], bytes):
                packet["decoded"]["payload"] = base64.b64encode(
                    packet["decoded"]["payload"]
                ).decode("utf-8")

        return packet

    def get_matrix_commands(self):
        """Get Matrix commands handled by this plugin.

        Returns:
            list: Empty list (this plugin handles all traffic, not specific commands)
        """
        return []

    def get_mesh_commands(self):
        """Get mesh commands handled by this plugin.

        Returns:
            list: Empty list (this plugin handles all traffic, not specific commands)
        """
        return []

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        """Handle incoming meshtastic message and relay to Matrix.

        Args:
            packet: Raw packet data (dict or JSON) to relay
            formatted_message (str): Human-readable message extracted from packet
            longname (str): Long name of the sender node
            meshnet_name (str): Name of the mesh network

        Returns:
            bool: Always returns False to allow other plugins to process the same packet

        Processes the packet by normalizing and preparing it, connects to the Matrix client,
        checks if the meshtastic channel is mapped to a Matrix room based on config,
        and sends the packet to the appropriate Matrix room.
        """
        from mmrelay.matrix_utils import connect_matrix

        packet = self.process(packet)
        matrix_client = await connect_matrix()

        packet_type = packet["decoded"]["portnum"]
        if "channel" in packet:
            channel = packet["channel"]
        else:
            channel = 0

        channel_mapped = False
        if config is not None:
            matrix_rooms = config.get("matrix_rooms", [])
            for room in matrix_rooms:
                if room["meshtastic_channel"] == channel:
                    channel_mapped = True
                    break

        if not channel_mapped:
            self.logger.debug(f"Skipping message from unmapped channel {channel}")
            return

        await matrix_client.room_send(
            room_id=room["id"],
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "mmrelay_suppress": True,
                "meshtastic_packet": json.dumps(packet),
                "body": f"Processed {packet_type} radio packet",
            },
        )

        return False

    def matches(self, event):
        """Check if Matrix event is a relayed radio packet.

        Args:
            event: Matrix room event object

        Returns:
            bool: True if event contains embedded meshtastic packet JSON

        Identifies Matrix messages that contain embedded meshtastic packet
        data by matching the default relay message format "Processed <portnum> radio packet".
        """
        # Check for the presence of necessary keys in the event
        content = event.source.get("content", {})
        body = content.get("body", "")

        if isinstance(body, str):
            match = re.match(r"^Processed (.+) radio packet$", body)
            return bool(match)
        return False

    async def handle_room_message(self, room, event, full_message):
        """Handle incoming Matrix room message and relay to meshtastic mesh.

        Args:
            room: Matrix Room object where message was received
            event: Matrix room event containing the message
            full_message (str): Raw message body text

        Returns:
            bool: True if packet relaying succeeded, False otherwise

        Checks if the Matrix event matches the expected embedded packet format,
        retrieves the packet JSON, decodes it, reconstructs a MeshPacket,
        connects to the meshtastic client, and sends the packet via the radio.
        """
        # Use the event for matching instead of full_message
        if not self.matches(event):
            return False

        channel = None
        if config is not None:
            matrix_rooms = config.get("matrix_rooms", [])
            for room_config in matrix_rooms:
                if room_config["id"] == room.room_id:
                    channel = room_config["meshtastic_channel"]

        if not channel:
            self.logger.debug(f"Skipping message from unmapped channel {channel}")
            return False

        packet_json = event.source["content"].get("meshtastic_packet")
        if not packet_json:
            self.logger.debug("Missing embedded packet")
            return False

        try:
            packet = json.loads(packet_json)
        except (json.JSONDecodeError, TypeError) as e:
            self.logger.error(f"Error processing embedded packet: {e}")
            return

        from mmrelay.meshtastic_utils import connect_meshtastic

        meshtastic_client = connect_meshtastic()
        meshPacket = mesh_pb2.MeshPacket()
        meshPacket.channel = channel
        meshPacket.decoded.payload = base64.b64decode(packet["decoded"]["payload"])
        meshPacket.decoded.portnum = packet["decoded"]["portnum"]
        meshPacket.decoded.want_response = False
        meshPacket.id = meshtastic_client._generatePacketId()

        self.logger.debug("Relaying packet to Radio")

        meshtastic_client._sendPacket(
            meshPacket=meshPacket, destinationId=packet["toId"]
        )
        return True
