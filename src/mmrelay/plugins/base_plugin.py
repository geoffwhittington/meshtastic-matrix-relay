import threading
import time
from abc import ABC, abstractmethod

import markdown
import schedule

from mmrelay.db_utils import (
    delete_plugin_data,
    get_plugin_data,
    get_plugin_data_for_node,
    store_plugin_data,
)
from mmrelay.log_utils import get_logger

# Global config variable that will be set from main.py
config = None


class BasePlugin(ABC):
    # Class-level default attributes
    plugin_name = None  # Must be overridden in subclasses
    max_data_rows_per_node = 100
    priority = 10

    @property
    def description(self):
        return ""

    def __init__(self) -> None:
        # IMPORTANT NOTE FOR PLUGIN DEVELOPERS:
        # When creating a plugin that inherits from BasePlugin, you MUST set
        # self.plugin_name in your __init__ method BEFORE calling super().__init__()
        # Example:
        #   def __init__(self):
        #       self.plugin_name = "your_plugin_name"  # Set this FIRST
        #       super().__init__()                     # Then call parent
        #
        # Failure to do this will cause command recognition issues and other problems.

        super().__init__()

        # Verify plugin_name is properly defined
        if not hasattr(self, "plugin_name") or self.plugin_name is None:
            raise ValueError(
                f"{self.__class__.__name__} is missing plugin_name definition. "
                f"Make sure to set self.plugin_name BEFORE calling super().__init__()"
            )

        self.logger = get_logger(f"Plugin:{self.plugin_name}")
        self.config = {"active": False}
        global config
        plugin_levels = ["plugins", "community-plugins", "custom-plugins"]

        # Check if config is available
        if config is not None:
            for level in plugin_levels:
                if level in config and self.plugin_name in config[level]:
                    self.config = config[level][self.plugin_name]
                    break

            # Get the list of mapped channels
            self.mapped_channels = [
                room.get("meshtastic_channel")
                for room in config.get("matrix_rooms", [])
            ]

        # Get the channels specified for this plugin, or default to all mapped channels
        self.channels = self.config.get("channels", self.mapped_channels)

        # Ensure channels is a list
        if not isinstance(self.channels, list):
            self.channels = [self.channels]

        # Validate the channels
        invalid_channels = [
            ch for ch in self.channels if ch not in self.mapped_channels
        ]
        if invalid_channels:
            self.logger.warning(
                f"Plugin '{self.plugin_name}': Channels {invalid_channels} are not mapped in configuration."
            )

        # Get the response delay from the meshtastic config only
        self.response_delay = 3  # Default value
        if config is not None:
            self.response_delay = config.get("meshtastic", {}).get(
                "plugin_response_delay", self.response_delay
            )

    def start(self):
        if "schedule" not in self.config or (
            "at" not in self.config["schedule"]
            and "hours" not in self.config["schedule"]
            and "minutes" not in self.config["schedule"]
        ):
            self.logger.debug(f"Started with priority={self.priority}")
            return

        # Schedule the background job based on the configuration
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
        pass  # Implement in subclass if needed

    def strip_raw(self, data):
        if isinstance(data, dict):
            data.pop("raw", None)
            for k, v in data.items():
                data[k] = self.strip_raw(v)
        elif isinstance(data, list):
            data = [self.strip_raw(item) for item in data]
        return data

    def get_response_delay(self):
        return self.response_delay

    # Modified method to accept is_direct_message parameter
    def is_channel_enabled(self, channel, is_direct_message=False):
        if is_direct_message:
            return True  # Always respond to DMs if the plugin is active
        else:
            return channel in self.channels

    def get_matrix_commands(self):
        return [self.plugin_name]

    async def send_matrix_message(self, room_id, message, formatted=True):
        from mmrelay.matrix_utils import matrix_client

        if matrix_client is None:
            self.logger.error("Matrix client is not initialized. Cannot send message.")
            return None

        return await matrix_client.room_send(
            room_id=room_id,
            message_type="m.room.message",
            content={
                "msgtype": "m.text",
                "format": "org.matrix.custom.html" if formatted else None,
                "body": message,
                "formatted_body": markdown.markdown(message) if formatted else None,
            },
        )

    def get_mesh_commands(self):
        return []

    def store_node_data(self, meshtastic_id, node_data):
        data = self.get_node_data(meshtastic_id=meshtastic_id)
        data = data[-self.max_data_rows_per_node :]
        if isinstance(node_data, list):
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

    def matches(self, event):
        from mmrelay.matrix_utils import bot_command

        # Pass the entire event to bot_command
        return bot_command(self.plugin_name, event)

    @abstractmethod
    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        pass  # Implement in subclass

    @abstractmethod
    async def handle_room_message(self, room, event, full_message):
        pass  # Implement in subclass
