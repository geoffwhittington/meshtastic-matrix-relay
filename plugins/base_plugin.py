from abc import ABC, abstractmethod


class BasePlugin(ABC):
    def configure(self, matrix_client, meshtastic_client) -> None:
        self.matrix_client = matrix_client
        self.meshtastic_client = meshtastic_client

    @abstractmethod
    async def handle_meshtastic_message(
        packet, formatted_message, longname, meshnet_name
    ):
        print("Base plugin: handling Meshtastic message")

    @abstractmethod
    async def handle_room_message(room, event, full_message):
        print("Base plugin: handling room message")
