import markdown
from abc import ABC, abstractmethod
from log_utils import get_logger
from config import relay_config
from db_utils import (
    store_plugin_data,
    get_plugin_data,
    get_plugin_data_for_node,
    delete_plugin_data,
)


class BasePlugin(ABC):
    plugin_name = None
    max_data_rows_per_node = 100
    priority = 10

    @property
    def description(self):
        return f""

    def __init__(self) -> None:
        super().__init__()
        self.logger = get_logger(f"Plugin:{self.plugin_name}")
        self.config = {"active": False}
        if "plugins" in relay_config and self.plugin_name in relay_config["plugins"]:
            self.config = relay_config["plugins"][self.plugin_name]

    def strip_raw(self, data):
        if type(data) is not dict:
            return data

        if "raw" in data:
            del data["raw"]

        for k, v in data.items():
            data[k] = self.strip_raw(v)

        return data

    def get_matrix_commands(self):
        return [self.plugin_name]

    async def send_matrix_message(self, room_id, message, formatted=True):
        from matrix_utils import connect_matrix

        matrix_client = await connect_matrix()

        return await matrix_client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "format": "org.matrix.custom.html" if formatted else None,
                "body": message,
                "formatted_body": markdown.markdown(message),
            },
        )

    def get_mesh_commands(self):
        return []

    def store_node_data(self, meshtastic_id, node_data):
        data = self.get_node_data(meshtastic_id=meshtastic_id)
        data = data[-self.max_data_rows_per_node :]
        if type(node_data) is list:
            data.extend(node_data)
        else:
            data.append(node_data)
        store_plugin_data(self.plugin_name, meshtastic_id, data)

    def set_node_data(self, meshtastic_id, node_data):
        node_data = node_data[-self.max_data_rows_per_node :]
        store_plugin_data(self.plugin_name, meshtastic_id, node_data)

    def delete_node_data(self, meshtastic_id):
        return delete_plugin_data(self.plugin_name, meshtastic_id)

    def get_node_data(self, meshtastic_id):
        return get_plugin_data_for_node(self.plugin_name, meshtastic_id)

    def get_data(self):
        return get_plugin_data(self.plugin_name)

    def matches(self, payload):
        from matrix_utils import bot_command

        if type(payload) == str:
            return bot_command(self.plugin_name, payload)
        return False

    @abstractmethod
    async def handle_meshtastic_message(
        packet, formatted_message, longname, meshnet_name
    ):
        print("Base plugin: handling Meshtastic message")

    @abstractmethod
    async def handle_room_message(room, event, full_message):
        print("Base plugin: handling room message")
