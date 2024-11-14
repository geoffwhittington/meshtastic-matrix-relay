import threading
import time
from abc import ABC, abstractmethod

import markdown
import schedule

from config import relay_config
from db_utils import (
    delete_plugin_data,
    get_plugin_data,
    get_plugin_data_for_node,
    store_plugin_data,
)
from log_utils import get_logger


class BasePlugin(ABC):
    plugin_name = None
    max_data_rows_per_node = 100
    priority = 10

    @property
    def description(self):
        return ""

    def __init__(self) -> None:
        super().__init__()
        self.logger = get_logger(f"Plugin:{self.plugin_name}")
        self.config = {"active": False}
        if "plugins" in relay_config and self.plugin_name in relay_config["plugins"]:
            self.config = relay_config["plugins"][self.plugin_name]

    def start(self):
        if "schedule" not in self.config or (
            "at" not in self.config["schedule"]
            and "hours" not in self.config["schedule"]
            and "minutes" not in self.config["schedule"]
        ):
            self.logger.debug(f"Started with priority={self.priority}")
            return

        # Schedule the email-checking function to run every minute
        if "at" in self.config["schedule"] and "hours" in self.config["schedule"]:
            schedule.every(self.config["schedule"]["hours"]).hours.at(
                self.config["schedule"]["at"]
            ).do(self.background_job)
        elif "at" in self.config["schedule"] and "minutes" in self.config["schedule"]:
            schedule.every(self.config["schedule"]["minutes"]).minutes.at(
                self.config["schedule"]["at"]
            ).do(self.background_job)
        elif "hours" in self.config["schedule"]:
            schedule.every(self.config["schedule"]["hours"]).hours.do(
                self.background_job
            )
        elif "minutes" in self.config["schedule"]:
            schedule.every(self.config["schedule"]["minutes"]).minutes.do(
                self.background_job
            )

        # Function to execute the scheduled tasks
        def run_schedule():
            while True:
                schedule.run_pending()
                time.sleep(1)

        # Create a thread for executing the scheduled tasks
        schedule_thread = threading.Thread(target=run_schedule)

        # Start the thread
        schedule_thread.start()
        self.logger.debug(f"Scheduled with priority={self.priority}")

    # trunk-ignore(ruff/B027)
    def background_job(self):
        pass

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

        if isinstance(payload, str):
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
