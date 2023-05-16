import re

from plugins.base_plugin import BasePlugin


class Plugin(BasePlugin):
    plugin_name = "ping"

    @property
    def description(self):
        return f"Check connectivity with the relay"

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        if (
            "decoded" in packet
            and "portnum" in packet["decoded"]
            and packet["decoded"]["portnum"] == "TEXT_MESSAGE_APP"
            and "text" in packet["decoded"]
        ):
            message = packet["decoded"]["text"]
            message = message.strip()
            if f"!{self.plugin_name}" not in message:
                return

            from meshtastic_utils import connect_meshtastic

            meshtastic_client = connect_meshtastic()
            meshtastic_client.sendText(text="pong!", destinationId=packet["fromId"])
            return True

    def get_matrix_commands(self):
        return [self.plugin_name]

    def get_mesh_commands(self):
        return [self.plugin_name]

    async def handle_room_message(self, room, event, full_message):
        full_message = full_message.strip()
        if not self.matches(full_message):
            return False

        from matrix_utils import connect_matrix

        matrix_client = await connect_matrix()
        response = await matrix_client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "body": "pong!",
            },
        )
        return True
