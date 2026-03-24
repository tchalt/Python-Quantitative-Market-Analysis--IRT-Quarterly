import yaml
import os

def load_config(config_path="config/config.yaml"):
    """
    Loads configuration from a YAML file.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)
