# Meshtastic <=> Matrix Relay

Simple relay between Meshtastic and a Matrix homeserver.

## Installation

Clone the repo

```
git clone https://github.com/geoffwhittington/meshtastic-matrix-relay.git
```

### Setup

In the directory create a Python virtualenv:

```
python3 -m venv .pyenv
```

Activate the virtualenv and install dependencies

```
source .pyenv/bin/activate
pip install -r requirements.txt
```

### Configuration

Create a `config.yaml` in the directory with the appropriate values. A sample is provided below:

```
matrix:
  homeserver: "https://example.matrix.org"
  access_token: "reaalllllyloooooongsecretttttcodeeeeeeforrrrbot"
  bot_user_id: "@botuser:example.matrix.org"
  room_id: "!someroomid:example.matrix.org"

meshtastic:
  connection_type: serial  # Choose either "network" or "serial"
  serial_port: /dev/ttyUSB0  # Only used when connection is "serial"
  host: "meshtastic.local" # Only used when connection is "network"
  channel: 0
  meshnet_name: "Your Meshnet Name" # This is displayed in full on Matrix, but is truncated when sent to a Meshnet
  display_meshnet_name: true

logging:
  level: "debug"
```

## Run

After activating the virtualenv:

```
source .pyenv/bin/activate
```

Run the following on the command-line:

```
python main.py
```

For example,

```
$ python main.py
INFO:meshtastic.matrix.relay:Starting Meshtastic <==> Matrix Relay...
INFO:meshtastic.matrix.relay:Connecting to radio at meshtastic.local ...
INFO:meshtastic.matrix.relay:Connected to radio at meshtastic.local.
INFO:meshtastic.matrix.relay:Listening for inbound radio messages ...
INFO:meshtastic.matrix.relay:Listening for inbound matrix messages ...
```
