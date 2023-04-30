import re
import statistics
from base_plugin import BasePlugin

from matrix_utils import connect_matrix
from meshtastic_utils import connect_meshtastic


class Plugin(BasePlugin):
    plugin_name = "health"

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        return

    async def handle_room_message(self, room, event, full_message):
        if not self.matrix_allowed(room, event):
            return

        meshtastic_client = connect_meshtastic()
        matrix_client = await connect_matrix()

        match = re.match(r"^.*: !health$", full_message)
        if match:
            battery_levels = []
            air_util_tx = []
            snr = []

            for node, info in meshtastic_client.nodes.items():
                if "deviceMetrics" in info:
                    battery_levels.append(info["deviceMetrics"]["batteryLevel"])
                    air_util_tx.append(info["deviceMetrics"]["airUtilTx"])
                if "snr" in info:
                    snr.append(info["snr"])

            low_battery = len([n for n in battery_levels if n <= 10])
            radios = len(meshtastic_client.nodes)
            avg_battery = statistics.mean(battery_levels) if battery_levels else 0
            mdn_battery = statistics.median(battery_levels)
            avg_air = statistics.mean(air_util_tx) if air_util_tx else 0
            mdn_air = statistics.median(air_util_tx)
            avg_snr = statistics.mean(snr) if snr else 0
            mdn_snr = statistics.median(snr)

            response = await matrix_client.room_send(
                room_id=room.room_id,
                message_type="m.room.message",
                content={
                    "msgtype": "m.text",
                    "body": f"""Nodes: {radios}
Battery: {avg_battery:.1f}% / {mdn_battery:.1f}% (avg / median)
Nodes with Low Battery (< 10): {low_battery}
Air Util: {avg_air:.2f} / {mdn_air:.2f} (avg / median)
SNR: {avg_snr:.2f} / {mdn_snr:.2f} (avg / median)
""",
                },
            )
