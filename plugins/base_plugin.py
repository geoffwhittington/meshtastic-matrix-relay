from abc import ABC, abstractmethod
from log_utils import get_logger
from config import relay_config
from db_utils import store_plugin_data, get_plugin_data, get_plugin_data_for_node


class BasePlugin(ABC):
    """
    Sample config

    plugin_name:
        active: true
        matrix_rooms:
        - id: "!room:host.matrix.org"
        matrix_users:
        - user@host.matrix.org
    """

    plugin_name = None
    max_data_rows_per_node = 10

    def __init__(self) -> None:
        super().__init__()
        self.logger = get_logger(f"Plugin:{self.plugin_name}")
        self.config = {"active": False}
        if "plugins" in relay_config and self.plugin_name in relay_config["plugins"]:
            self.config = relay_config["plugins"][self.plugin_name]

    def store_node_data(self, meshtastic_id, data):
        data = data[-self.max_data_rows_per_node :]
        store_plugin_data(self.plugin_name, meshtastic_id, data)

    def get_node_data(self, meshtastic_id):
        return get_plugin_data_for_node(self.plugin_name, meshtastic_id)

    def get_data(self):
        return get_plugin_data(self.plugin_name)

    def matrix_allowed(self, matrix_room, event):
        allowed = True
        if "matrix_rooms" in self.config:
            allowed = False
            for matrix_room in self.config["matrix_rooms"]:
                if matrix_room["id"] == matrix_room.room_id:
                    allowed = True

        if allowed and "matrix_users" in self.config:
            allowed = False
            for matrix_user in self.config["matrix_users"]:
                if matrix_user == event.sender:
                    allowed = True

        return allowed

    @abstractmethod
    async def handle_meshtastic_message(
        packet, formatted_message, longname, meshnet_name
    ):
        print("Base plugin: handling Meshtastic message")

    @abstractmethod
    async def handle_room_message(room, event, full_message):
        print("Base plugin: handling room message")
