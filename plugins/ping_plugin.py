from plugins.base_plugin import BasePlugin
import re

class Plugin(BasePlugin):
    plugin_name = "ping"

    @property
    def description(self):
        return "Check connectivity with the relay or respond to pings over the mesh"

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        if "decoded" in packet and "text" in packet["decoded"]:
            message = packet["decoded"]["text"].strip()

            # Match "ping" followed by optional punctuation
            match = re.search(r"\b(ping[!?]*)\b", message, re.IGNORECASE)
            if match:
                from meshtastic_utils import connect_meshtastic

                meshtastic_client = connect_meshtastic()
                channel = packet.get("channel", 0)  # Default to channel 0 if not provided

                # Extract matched text
                matched_text = match.group(1)

                # Define the base response
                base_response = "pong"

                # Preserve case of the matched word
                if matched_text.isupper():
                    base_response = base_response.upper()
                elif matched_text[0].isupper():
                    base_response = base_response.capitalize()

                # Extract and preserve punctuation from the matched text
                punctuation = matched_text[len("ping"):]  # Punctuation after "ping"

                # If there are more than 5 punctuation marks, default to "Pong..."
                if len(punctuation) > 5:
                    reply_message = "Pong..."
                else:
                    reply_message = base_response + punctuation

                # Send the reply back to the same channel
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
