import re

from plugins.base_plugin import BasePlugin
from plugin_loader import load_plugins


class Plugin(BasePlugin):
    plugin_name = "help"

    @property
    def description(self):
        return f"List supported relay commands"

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        return False

    def get_matrix_commands(self):
        return [self.plugin_name]

    def get_mesh_commands(self):
        return []

    async def handle_room_message(self, room, event, full_message):
        full_message = full_message.strip()
        if not self.matches(full_message):
            return False

        command = None

        match = re.match(r"^.*: !help\s+(.+)$", full_message)
        if match:
            command = match.group(1)

        plugins = load_plugins()

        if command:
            reply = f"No such command: {command}"

            for plugin in plugins:
                if command in plugin.get_matrix_commands():
                    reply = f"{command}: {plugin.description}"
        else:
            commands = []
            for plugin in plugins:
                commands.extend(plugin.get_matrix_commands())
            reply = "Commands: " + ", ".join(commands)

        from matrix_utils import connect_matrix

        matrix_client = await connect_matrix()

        response = await matrix_client.room_send(
            room_id=room.room_id,
            message_type="m.room.message",
            content={"msgtype": "m.text", "body": reply},
        )
        return True
