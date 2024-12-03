import re
import string
import asyncio
from plugins.base_plugin import BasePlugin

def match_case(source, target):
    return ''.join(
        c.upper() if s.isupper() else c.lower()
        for s, c in zip(source, target)
    )

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
            channel = packet.get("channel", 0)  # Default to channel 0 if not provided

            if not self.is_channel_enabled(channel):
                self.logger.debug(f"Channel {channel} not enabled for plugin '{self.plugin_name}'")
                return False

            # Updated regex to match optional punctuation before and after "ping"
            match = re.search(
                r"(?<!\w)([!?]*)(ping)([!?]*)(?!\w)", message, re.IGNORECASE
            )
            if match:
                from meshtastic_utils import connect_meshtastic

                meshtastic_client = connect_meshtastic()

                # Extract matched text and punctuation
                pre_punc = match.group(1)
                matched_text = match.group(2)
                post_punc = match.group(3)

                total_punc_length = len(pre_punc) + len(post_punc)

                # Define the base response
                base_response = "pong"

                # Adjust base_response to match the case pattern of matched_text
                base_response = match_case(matched_text, base_response)

                # Construct the reply message
                if total_punc_length > 5:
                    reply_message = "Pong..."
                else:
                    reply_message = pre_punc + base_response + post_punc

                # Wait for the response delay
                await asyncio.sleep(self.get_response_delay())

                # Send the reply back to the same channel
                meshtastic_client.sendText(text=reply_message, channelIndex=channel)
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
