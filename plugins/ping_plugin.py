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
            if re.search(r"\bping\b", message, re.IGNORECASE) or "!ping" in message:
                from meshtastic_utils import connect_meshtastic

                meshtastic_client = connect_meshtastic()
                channel = packet.get("channel", 0)  # Default to channel 0 if not provided
                reply_message = "pong!"
                if longname:
                    reply_message = f"{longname}: pong!"

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
