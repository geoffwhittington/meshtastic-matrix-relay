import re
import statistics
from plugins.base_plugin import BasePlugin
from datetime import datetime


def get_relative_time(timestamp):
    now = datetime.now()
    dt = datetime.fromtimestamp(timestamp)

    # Calculate the time difference between the current time and the given timestamp
    delta = now - dt

    # Extract the relevant components from the time difference
    days = delta.days
    seconds = delta.seconds

    # Convert the time difference into a relative timeframe
    if days > 7:
        return dt.strftime(
            "%b %d, %Y"
        )  # Return the timestamp in a specific format if it's older than 7 days
    elif days >= 1:
        return f"{days} days ago"
    elif seconds >= 3600:
        hours = seconds // 3600
        return f"{hours} hours ago"
    elif seconds >= 60:
        minutes = seconds // 60
        return f"{minutes} minutes ago"
    else:
        return "Just now"


class Plugin(BasePlugin):
    plugin_name = "nodes"

    @property
    def description(self):
        return """Show mesh radios and node data

$shortname $longname / $devicemodel / $battery $voltage / $snr / $lastseen
"""

    def generate_response(self):
        from meshtastic_utils import connect_meshtastic

        meshtastic_client = connect_meshtastic()

        response = f">**Nodes: {len(meshtastic_client.nodes)}**"

        for node, info in meshtastic_client.nodes.items():
            snr = ""
            if "snr" in info:
                if info['snr'] is not None:
                    snr = f"{info['snr']} dB "

            last_heard = None
            if "lastHeard" in info:
                last_heard = get_relative_time(info["lastHeard"])

            voltage = ""
            battery = ""
            if "deviceMetrics" in info:
                if "voltage" in info["deviceMetrics"]:
                    voltage = f"{info['deviceMetrics']['voltage']}V "
                if "batteryLevel" in info["deviceMetrics"]:
                    battery = f"{info['deviceMetrics']['batteryLevel']}% "

            response += f"\n\n>**{info['user']['shortName']}** {info['user']['longName']}\n"\
                        f">{info['user']['hwModel']} {battery}{voltage}\n"\
                        f">{snr}{last_heard}"

        return response

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        return False

    async def handle_room_message(self, room, event, full_message):
        from matrix_utils import connect_matrix

        full_message = full_message.strip()
        if not self.matches(full_message):
            return False

        response = await self.send_matrix_message(
            room_id=room.room_id, message=self.generate_response(), formatted=False
        )

        return True
