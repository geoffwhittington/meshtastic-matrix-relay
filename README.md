# Meshtastic <=> Matrix Relay

A powerful and easy-to-use relay between Meshtastic devices and Matrix chat rooms, allowing seamless communication across platforms. This opens the door for bridging Meshtastic devices to [many other platforms](https://matrix.org/bridges/).

## Features

- Bidirectional message relay between Meshtastic devices and Matrix chat rooms, capable of supporting multiple meshnets
- Supports both serial and network connections for Meshtastic devices
- Custom keys are embedded in Matrix messages which are used when relaying messages between two or more meshnets.
- Truncates long messages to fit within Meshtastic's payload size
- SQLite database to store Meshtastic longnames for improved functionality
- Customizable logging level for easy debugging
- Configurable through a simple YAML file
- **New:** Supports mapping multiple rooms and channels 1:1

### Windows Installer

<img src="https://user-images.githubusercontent.com/1770544/235249050-8c79107a-50cc-4803-b989-39e58100342d.png" width="500"/>

### Plugins

Generate a map of your nodes

<img src="https://user-images.githubusercontent.com/1770544/235247915-47750b4f-d505-4792-a458-54a5f24c1523.png" width="500"/>

Produce high-level details about your mesh

<img src="https://user-images.githubusercontent.com/1770544/235245873-1ddc773b-a4cd-4c67-b0a5-b55a29504b73.png" width="500"/>

## Installation

Clone the repository:

```
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
```

### Setup

Create a Python virtual environment in the project directory:

```
python3 -m venv .pyenv
```

Activate the virtual environment and install dependencies:

```
source .pyenv/bin/activate
pip install -r requirements.txt
```


### Configuration

Create a `config.yaml` in the project directory with the appropriate values. A sample configuration is provided below:

```yaml
matrix:
  homeserver: "https://example.matrix.org"
  access_token: "reaalllllyloooooongsecretttttcodeeeeeeforrrrbot"
  bot_user_id: "@botuser:example.matrix.org"

matrix_rooms:  # Needs at least 1 room & channel, but supports all Meshtastic channels
  - id: "!someroomid:example.matrix.org"
    meshtastic_channel: 0
  - id: "!someroomid2:example.matrix.org"
    meshtastic_channel: 2

meshtastic:
  connection_type: serial  # Choose either "network" or "serial"
  serial_port: /dev/ttyUSB0  # Only used when connection is "serial"
  host: "meshtastic.local" # Only used when connection is "network"
  meshnet_name: "VeryCoolMeshnet" # This is displayed in full on Matrix, but is truncated when sent to a Meshnet
  broadcast_enabled: true

logging:
  level: "info"
  show_timestamps: true
  timestamp_format: '[%H:%M:%S]'
```

## Usage
Activate the virtual environment:
```
source .pyenv/bin/activate
```
Run the `main.py` script:
```
python main.py
```
Example output:
```

$ python main.py
INFO:meshtastic.matrix.relay:Starting Meshtastic <==> Matrix Relay...
INFO:meshtastic.matrix.relay:Connecting to radio at meshtastic.local ...
INFO:meshtastic.matrix.relay:Connected to radio at meshtastic.local.
INFO:meshtastic.matrix.relay:Listening for inbound radio messages ...
INFO:meshtastic.matrix.relay:Listening for inbound matrix messages ...
INFO:meshtastic.matrix.relay:Processing matrix message from @bob:matrix.org: Hi Alice!
INFO:meshtastic.matrix.relay:Sending radio message from Bob to radio broadcast
INFO:meshtastic.matrix.relay:Processing inbound radio message from !613501e4 on channel 0
INFO:meshtastic.matrix.relay:Relaying Meshtastic message from Alice to Matrix: [Alice/VeryCoolMeshnet]: Hey Bob!
INFO:meshtastic.matrix.relay:Sent inbound radio message to matrix room: !someroomid:example.matrix.org
```
