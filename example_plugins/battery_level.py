import json
import io
import re
import matplotlib.pyplot as plt
from PIL import Image
from datetime import datetime, timedelta

from plugins.base_plugin import BasePlugin
from matrix_utils import connect_matrix, upload_image, send_room_image


class Plugin(BasePlugin):
    plugin_name = "telemetry"
    max_data_rows_per_node = 50

    def _generate_timeperiods(self, hours=12):
        # Calculate the start and end times
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # Create a list of hourly intervals for the last 12 hours
        hourly_intervals = []
        current_time = start_time
        while current_time <= end_time:
            hourly_intervals.append(current_time)
            current_time += timedelta(hours=1)
        return hourly_intervals

    async def handle_meshtastic_message(
        self, packet, formatted_message, longname, meshnet_name
    ):
        if (
            "decoded" in packet
            and "portnum" in packet["decoded"]
            and packet["decoded"]["portnum"] == "TELEMETRY_APP"
        ):
            telemetry_data = []
            data = self.get_node_data(meshtastic_id=packet["fromId"])
            if data:
                telemetry_data = data
            packet_data = packet["decoded"]["telemetry"]

            telemetry_data.append(
                {
                    "time": packet_data["time"],
                    "batteryLevel": packet_data["deviceMetrics"]["batteryLevel"],
                    "voltage": packet_data["deviceMetrics"]["voltage"],
                    "airUtilTx": packet_data["deviceMetrics"]["airUtilTx"],
                }
            )
            self.store_node_data(meshtastic_id=packet["fromId"], data=telemetry_data)
            return True

    async def handle_room_message(self, room, event, full_message):
        self.logger.debug("Hello world, Matrix")

        hourly_intervals = self._generate_timeperiods()
        matrix_client = await connect_matrix()

        # Compute the hourly averages for each node
        hourly_averages = {}

        match = re.match(r"^.*: !battery$", full_message)
        # Indicate this message is not meant for this plugin
        if not match:
            return False

        for node_data_json in self.get_data():
            node_data_rows = json.loads(node_data_json[0])

            for record in node_data_rows:
                record_time = datetime.fromtimestamp(
                    record["time"]
                )  # Replace with your timestamp field name
                battery_level = record[
                    "batteryLevel"
                ]  # Replace with your battery level field name
                for i in range(len(hourly_intervals) - 1):
                    if hourly_intervals[i] <= record_time < hourly_intervals[i + 1]:
                        if i not in hourly_averages:
                            hourly_averages[i] = []
                        hourly_averages[i].append(battery_level)
                        break

        # Compute the final hourly averages
        final_averages = {}
        for i, interval in enumerate(hourly_intervals[:-1]):
            if i in hourly_averages:
                final_averages[interval] = sum(hourly_averages[i]) / len(
                    hourly_averages[i]
                )
            else:
                final_averages[interval] = 0.0

        # Extract the hourly intervals and average values into separate lists
        hourly_intervals = list(final_averages.keys())
        average_values = list(final_averages.values())

        # Convert the hourly intervals to strings
        hourly_strings = [hour.strftime("%H") for hour in hourly_intervals]

        # Create the plot
        fig, ax = plt.subplots()
        ax.plot(hourly_strings, average_values)

        # Set the plot title and axis labels
        ax.set_title("Hourly Battery Level Averages")
        ax.set_xlabel("Hour")
        ax.set_ylabel("Battery Level")

        # Rotate the x-axis labels for readability
        plt.xticks(rotation=45)

        # Save the plot as a PIL image
        buf = io.BytesIO()
        fig.canvas.print_png(buf)
        buf.seek(0)
        img = Image.open(buf)
        pil_image = Image.frombytes(mode="RGBA", size=img.size, data=img.tobytes())

        upload_response = await upload_image(matrix_client, pil_image, "graph.png")
        await send_room_image(matrix_client, room.room_id, upload_response)
        return True