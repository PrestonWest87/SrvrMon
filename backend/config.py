# backend/config.py
import yaml
import os
import logging

logger = logging.getLogger(__name__)

def load_app_config(config_file_path='config.yaml'):
    """
    Loads application configuration from a YAML file.

    Args:
        config_file_path (str): Path to the YAML configuration file. 
                                Defaults to 'config.yaml' in the project root.

    Returns:
        dict: Loaded configuration dictionary, or an empty dict if file not found or malformed.
    """
    # Construct path relative to project root (assuming this file is in backend/)
    # The project root is one level up from the directory containing this config.py
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    actual_config_path = os.path.join(project_root, config_file_path)

    if not os.path.exists(actual_config_path):
        logger.debug(f"Configuration file not found at: {actual_config_path}")
        return {}

    try:
        with open(actual_config_path, 'r') as f:
            config = yaml.safe_load(f)
        if config is None: # Handle empty YAML file
            logger.info(f"Configuration file is empty: {actual_config_path}")
            return {}
        logger.info(f"Successfully loaded configuration from: {actual_config_path}")
        return config
    except FileNotFoundError: # Should be caught by os.path.exists, but as a fallback
        logger.debug(f"Configuration file not found (FileNotFoundError): {actual_config_path}")
        return {}
    except yaml.YAMLError as e:
        logger.warning(f"Error parsing YAML configuration file {actual_config_path}: {e}")
        return {}
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading config {actual_config_path}: {e}")
        return {}

if __name__ == '__main__':
    # Example usage for testing
    # Create a dummy config.yaml in the project root for this to work
    # e.g., ../config.yaml relative to this file if run directly
    
    # To test this, you'd temporarily create a config.yaml in the project root, e.g.,
    # polling_interval_ms: 2500
    # storage_paths:
    #  - "/test"
    # log_config:
    #  - name: "Test Log"
    #    path: "/var/log/test.log"

    print(f"Attempting to load config from default path 'config.yaml' (relative to project root).")
    cfg = load_app_config()
    print(f"Loaded config: {cfg}")

    # Example of how it might be used
    polling = cfg.get('polling_interval_ms', 1000)
    print(f"Polling interval from config (or default): {polling}")

    stor_paths = cfg.get('storage_paths', ['/default'])
    print(f"Storage paths from config (or default): {stor_paths}")

    log_cfg = cfg.get('log_config', [])
    print(f"Log config from config (or default): {log_cfg}")
