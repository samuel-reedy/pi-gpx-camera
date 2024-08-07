import os
import json
import logging
from filelock import FileLock

class ConfigHandler:
    def __init__(self, config_file):
        self.config_file = config_file
        self.lock_file = f"{config_file}.lock"
        self.config = self.load_config()

    def load_config(self):
        with FileLock(self.lock_file):
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as file:
                    content = file.read()
                    if not content.strip():
                        logging.warning(f"Config file {self.config_file} is empty.")
                        return {}
                    return json.loads(content)
            logging.warning(f"Config file {self.config_file} does not exist.")
            return {}

    def save_config(self):
        with FileLock(self.lock_file):
            with open(self.config_file, 'w') as file:
                json.dump(self.config, file, indent=4)

    def get(self, key, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        return value

    def set(self, key, value):
        if not self.config:
            print("Warning: The JSON configuration file is empty.")

        keys = key.split('.')
        d = self.config

        for k in keys[:-1]:
            if k not in d or not isinstance(d[k], dict):
                print(f"Warning: Overwriting non-dict value at key '{k}'")
                d[k] = {}
            d = d[k]
        d[keys[-1]] = value
        self.save_config()

# Initialize the ConfigHandler with the path to your config.json
config_path = os.path.join(os.path.dirname(__file__), '../../config.json')
config = ConfigHandler(config_path)