# backend/app.py

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
# `eventlet.monkey_patch()` is called in run.py before this module is imported.
from backend.collectors import get_all_stats 
from backend.config import load_app_config # Import config loader
import os
from flask import request # For accessing request context in SocketIO events
import logging

logger = logging.getLogger(__name__)

# Initialize Flask app and SocketIO
app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# --- Load Application Configuration ---
app_config = load_app_config() # Load from config.yaml

# --- Determine POLLING_INTERVAL_MS ---
polling_interval_ms = 2000 # Default
if 'polling_interval_ms' in app_config and isinstance(app_config['polling_interval_ms'], int):
    polling_interval_ms = app_config['polling_interval_ms']
    logger.info(f"Polling interval loaded from config.yaml: {polling_interval_ms}ms")

polling_interval_ms_env = os.environ.get('POLLING_INTERVAL_MS')
if polling_interval_ms_env:
    try:
        polling_interval_ms = int(polling_interval_ms_env)
        logger.info(f"Polling interval overridden by environment variable POLLING_INTERVAL_MS: {polling_interval_ms}ms")
    except ValueError:
        logger.warning(f"Invalid POLLING_INTERVAL_MS env var: '{polling_interval_ms_env}'. Using previous value: {polling_interval_ms}ms.")

if polling_interval_ms < 500:
    logger.warning(f"Polling interval {polling_interval_ms}ms is too low. Setting to 500ms.")
    polling_interval_ms = 500
logger.info(f"Effective polling interval: {polling_interval_ms}ms")
POLLING_INTERVAL_S = polling_interval_ms / 1000.0


# --- Determine STORAGE_PATHS_TO_MONITOR ---
storage_paths = ['/'] # Default
if os.path.exists('/host_root'): # Common pattern for mounting host root
    storage_paths = ['/host_root']
logger.debug(f"Initial default storage paths: {storage_paths}")

if 'storage_paths' in app_config and isinstance(app_config['storage_paths'], list):
    config_storage_paths = [str(p).strip() for p in app_config['storage_paths'] if str(p).strip()]
    if config_storage_paths:
        storage_paths = config_storage_paths
        logger.info(f"Storage paths loaded from config.yaml: {storage_paths}")
    else:
        logger.warning("storage_paths in config.yaml is empty or invalid. Using default: %s", storage_paths)


env_storage_paths_str = os.environ.get('STORAGE_PATHS')
if env_storage_paths_str:
    env_storage_paths_list = [path.strip() for path in env_storage_paths_str.split(',') if path.strip()]
    if env_storage_paths_list:
        storage_paths = env_storage_paths_list
        logger.info(f"Storage paths overridden by environment variable STORAGE_PATHS: {storage_paths}")
    else:
        logger.warning(f"STORAGE_PATHS environment variable was set but empty or invalid. Using derived/config/default: {storage_paths}.")
STORAGE_PATHS_TO_MONITOR = storage_paths
logger.info(f"Effective monitoring storage paths: {STORAGE_PATHS_TO_MONITOR}")


# --- Determine LOG_FILES_TO_MONITOR ---
log_files = [ # Default
    {'name': 'Container Dummy Log 1', 'path': '/app/dummy_log1.log'},
    {'name': 'Container Dummy Log 2', 'path': '/app/dummy_log2.log'}
]
logger.debug(f"Initial default log files: {log_files}")

if 'log_config' in app_config and isinstance(app_config['log_config'], list):
    valid_config_logs = []
    for item in app_config['log_config']:
        if isinstance(item, dict) and 'name' in item and 'path' in item:
            name = str(item['name']).strip()
            path = str(item['path']).strip()
            if name and path:
                valid_config_logs.append({'name': name, 'path': path})
            else:
                logger.warning("Skipping log_config item with empty name or path in config.yaml: %s", item)
        else:
            logger.warning("Skipping invalid log_config item in config.yaml (must be dict with name & path): %s", item)
    if valid_config_logs:
        log_files = valid_config_logs
        logger.info(f"Log files loaded from config.yaml: {log_files}")
    elif app_config['log_config']: # if log_config was present but all items were invalid
        logger.warning("log_config in config.yaml was present but contained no valid items. Using default log files: %s", log_files)


env_log_config_str = os.environ.get('LOG_CONFIG')
if env_log_config_str:
    user_logs_config_env = []
    try:
        configs_str_list = env_log_config_str.split(',')
        for config_item_str in configs_str_list:
            if ':' not in config_item_str: 
                logger.warning(f"Skipping invalid LOG_CONFIG environment variable item '{config_item_str}'. Expected format 'Name:Path'.")
                continue
            name, path = config_item_str.split(':', 1)
            name = name.strip()
            path = path.strip()
            if name and path:
                user_logs_config_env.append({'name': name, 'path': path})
            else:
                logger.warning(f"Skipping LOG_CONFIG environment variable item with empty name or path: '{config_item_str}'")

        if user_logs_config_env: 
            log_files = user_logs_config_env
            logger.info(f"Log files overridden by environment variable LOG_CONFIG: {log_files}")
        elif env_log_config_str: # LOG_CONFIG was set but resulted in no valid configurations
             logger.warning(f"LOG_CONFIG environment variable was set ('{env_log_config_str}') but no valid configurations found. Using derived/config/default: {log_files}")
    except Exception as e: 
        logger.warning(f"Error parsing LOG_CONFIG environment variable: %s. Using derived/config/default: %s", e, log_files)
LOG_FILES_TO_MONITOR = log_files
logger.info(f"Effective monitoring log files: {LOG_FILES_TO_MONITOR}")

# --- Create dummy log files (if configured and not existing) ---
for log_conf in LOG_FILES_TO_MONITOR:
    if 'dummy_log' in log_conf.get('path', '').lower() and not os.path.exists(log_conf.get('path', '')):
        try:
            with open(log_conf['path'], 'w') as f:
                f.write(f"Dummy log '{log_conf['name']}' started for JS monitor at {time.strftime('%Y-%m-%d %H:%M:%S')}.\n")
            logger.info(f"Created dummy log: {log_conf['path']}")
        except Exception as e:
            logger.error(f"Error creating dummy log {log_conf['path']}: %s", e)


# Background thread for emitting statistics
def background_thread():
    """Periodically fetches stats and emits them via WebSocket."""
    logger.info("Starting background stats emitter...")
    count = 0 # Counter for dummy log entries
    while True:
        # Simulate log activity for dummy logs if they are part of the active configuration
        for log_conf in LOG_FILES_TO_MONITOR:
            if 'dummy_log' in log_conf.get('path', '').lower() and os.path.exists(log_conf.get('path', '')):
                try:
                    with open(log_conf['path'], 'a') as f:
                        f.write(f"Log entry {count} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    # Limit dummy log size to prevent excessive growth
                    if os.path.getsize(log_conf['path']) > 1024 * 10: # 10KB limit per dummy log
                        with open(log_conf['path'], 'r+') as f:
                            lines = f.readlines()
                            f.seek(0); f.truncate() # Clear file
                            f.writelines(lines[-100:]) # Write back last 100 lines
                except Exception as e:
                    logger.error(f"Error writing to or trimming dummy log {log_conf['path']}: %s", e)
        
        # Gather all statistics
        current_stats = get_all_stats( # Pass the dynamically determined configs
            log_files_to_monitor=LOG_FILES_TO_MONITOR,
            storage_paths_to_monitor=STORAGE_PATHS_TO_MONITOR
        )
        # Emit stats to all connected clients
        socketio.emit('update_stats', current_stats)
        # logger.debug(f"Stats emitted at {current_stats['timestamp']}") 
        count += 1
        
        socketio.sleep(POLLING_INTERVAL_S) # Use the globally determined polling interval

# Flask route for the main page
@app.route('/')
def index():
    """Serves the main HTML page."""
    # Pass the effective polling interval to the template
    return render_template('index.html', polling_interval_ms=polling_interval_ms)

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    logger.info(f'Client connected: {request.sid}') 
    # Start the background thread only once using a Flask app context global
    # This ensures the thread isn't restarted on every new connection if it's already running.
    if not hasattr(app, 'stats_thread_started_flag') or not app.stats_thread_started_flag:
        socketio.start_background_task(target=background_thread)
        app.stats_thread_started_flag = True 
        logger.info("Background stats emitter thread started.")
    else:
        logger.info("Background stats emitter thread already running.")
    
    # Send initial full data dump to the newly connected client
    initial_stats = get_all_stats(
        log_files_to_monitor=LOG_FILES_TO_MONITOR,
        storage_paths_to_monitor=STORAGE_PATHS_TO_MONITOR
    )
    emit('update_stats', initial_stats) # Emit only to the connecting client

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections."""
    logger.info(f'Client disconnected: {request.sid}')

# The `if __name__ == '__main__':` block for `socketio.run(app, ...)`
# is now in `run.py`, which is the entrypoint specified in the Dockerfile's CMD.
