from abc import ABC, abstractmethod


class BasePlugin(ABC):
    @abstractmethod
    async def handle_meshtastic_message(
        packet, formatted_message, longname, meshnet_name
    ):
        print("Base plugin: handling Meshtastic message")

    @abstractmethod
    async def handle_room_message(room, event, full_message):
        print("Base plugin: handling room message")
