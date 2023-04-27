import yaml
from yaml.loader import SafeLoader

relay_config = {}
with open("config.yaml", "r") as f:
    relay_config = yaml.load(f, Loader=SafeLoader)
