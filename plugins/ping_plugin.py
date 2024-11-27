import re
import string
import logging
from plugins.base_plugin import BasePlugin

class Plugin(BasePlugin):
    plugin_name = "ping"
    punctuation = string.punctuation

    @property
    def description(self):
        return "Check connectivity with the relay or respond to pings over the mesh"

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        if "decoded" in packet and "text" in packet["decoded"]:
            message = packet["decoded"]["text"].strip()

            # Create a regex pattern that matches "ping" followed by 0-5 punctuation marks
            pattern = rf"\b(ping[{re.escape(string.punctuation)}]{{0,5}})\b"
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                from meshtastic_utils import connect_meshtastic

                meshtastic_client = connect_meshtastic()
                channel = packet.get("channel", 0)  # Default to channel 0 if not provided

                matched_text = match.group(1)

                base_response = "pong"

                # Preserve case of the matched word
                if matched_text.isupper():
                    base_response = base_response.upper()
                elif matched_text[0].isupper():
                    base_response = base_response.capitalize()

                # Extract punctuation from the matched text
                punctuation_part = re.sub(r'^ping', '', matched_text, flags=re.IGNORECASE)
                if len(punctuation_part) > 5:
                    reply_message = "Pong..."
                else:
                    reply_message = base_response + punctuation_part

                # Send the reply back to the same channel
                try:
                    meshtastic_client.sendText(
                        text=reply_message, channelIndex=channel
                    )
                return True

    def get_matrix_commands(self):
        return [self.plugin_name]

    def get_mesh_commands(self):
        return [self.plugin_name]

    async def handle_room_message(self, room, event, full_message):
        full_message = full_message.strip()
        if not self.matches(full_message):
            return False

        await self.send_matrix_message(room.room_id, "pong!")
        return True