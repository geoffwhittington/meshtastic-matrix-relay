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

            # Match "ping" anywhere in the message with optional punctuation
            match = re.search(r"\b(ping[\?!]{0,5})\b", message, re.IGNORECASE)
            if match:
                from meshtastic_utils import connect_meshtastic

                meshtastic_client = connect_meshtastic()
                channel = packet.get("channel", 0)  # Default to channel 0 if not provided

                # Get the matched case and punctuation
                matched_text = match.group(1)
                base_response = "pong"
                if len(re.findall(r"[!?]", matched_text)) > 5:
                    reply_message = "Pong..."
                else:
                    # Preserve case and punctuation
                    reply_message = re.sub(r"ping", base_response, matched_text, flags=re.IGNORECASE)

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
