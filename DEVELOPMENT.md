# Development

You can run the relay using Python 3.9 on Linux, MacOS, and Windows. We would enjoy pull requests to fix or enhance the relay

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
