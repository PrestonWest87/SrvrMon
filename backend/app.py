# backend/app.py

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
# `eventlet.monkey_patch()` is called in run.py before this module is imported.
from backend.collectors import get_all_stats 
import os
from flask import request # For accessing request context in SocketIO events

# Initialize Flask app and SocketIO
# The template_folder and static_folder are relative to this app.py file's location.
# Since app.py is in 'backend', '../frontend' correctly points to 'project_root/frontend'.
app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')
app.config['SECRET_KEY'] = os.urandom(24) # Used for session security by Flask-SocketIO
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*") # Allow all origins for simplicity

# --- Configuration for monitored items ---

# Storage paths to monitor (paths inside the container)
# Default to container's root. Can be overridden by STORAGE_PATHS environment variable.
# Example: STORAGE_PATHS="/,/mnt/data1,/mnt/data2"
DEFAULT_STORAGE_PATHS = ['/']
if os.path.exists('/host_root'): # Common pattern for mounting host root
    DEFAULT_STORAGE_PATHS = ['/host_root']

STORAGE_PATHS_TO_MONITOR = DEFAULT_STORAGE_PATHS
if 'STORAGE_PATHS' in os.environ:
    env_storage_paths = [path.strip() for path in os.environ['STORAGE_PATHS'].split(',') if path.strip()]
    if env_storage_paths:
        STORAGE_PATHS_TO_MONITOR = env_storage_paths
    else:
        print(f"Warning: STORAGE_PATHS environment variable was set but empty or invalid. Defaulting to {DEFAULT_STORAGE_PATHS}.")
print(f"Monitoring storage paths: {STORAGE_PATHS_TO_MONITOR}")


# Log files to monitor (paths inside the container)
# Can be overridden by LOG_CONFIG environment variable.
# Example: LOG_CONFIG="Syslog:/mnt/logs/syslog.log,Auth Log:/mnt/logs/auth.log"
DEFAULT_LOG_FILES = [
    {'name': 'Container Dummy Log 1', 'path': '/app/dummy_log1.log'},
    {'name': 'Container Dummy Log 2', 'path': '/app/dummy_log2.log'}
]
LOG_FILES_TO_MONITOR = DEFAULT_LOG_FILES
if 'LOG_CONFIG' in os.environ:
    user_logs_config = []
    try:
        configs_str = os.environ['LOG_CONFIG'].split(',')
        for config_item_str in configs_str:
            if ':' not in config_item_str: 
                print(f"Warning: Skipping invalid LOG_CONFIG item '{config_item_str}'. Expected format 'Name:Path'.")
                continue
            name, path = config_item_str.split(':', 1) 
            user_logs_config.append({'name': name.strip(), 'path': path.strip()})
        
        if user_logs_config: 
            LOG_FILES_TO_MONITOR = user_logs_config
            print(f"Using user-defined log files: {LOG_FILES_TO_MONITOR}")
        else:
            print("Warning: LOG_CONFIG was set but no valid configurations found. Using default dummy logs.")
    except Exception as e: 
        print(f"Warning: Error parsing LOG_CONFIG environment variable: {e}. Using default dummy logs.")

# Create dummy log files for demonstration if they are in the active config and don't exist
# In a real scenario, these would be actual log files you mount into the container.
for log_conf in LOG_FILES_TO_MONITOR:
    if 'dummy_log' in log_conf.get('path', '').lower() and not os.path.exists(log_conf.get('path', '')):
        try:
            with open(log_conf['path'], 'w') as f:
                f.write(f"Dummy log '{log_conf['name']}' started for JS monitor at {time.strftime('%Y-%m-%d %H:%M:%S')}.\n")
            print(f"Created dummy log: {log_conf['path']}")
        except Exception as e:
            print(f"Error creating dummy log {log_conf['path']}: {e}")


# Background thread for emitting statistics
def background_thread():
    """Periodically fetches stats and emits them via WebSocket."""
    print("Starting background stats emitter...")
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
                    print(f"Error writing to or trimming dummy log {log_conf['path']}: {e}")
        
        # Gather all statistics
        current_stats = get_all_stats(
            log_files_to_monitor=LOG_FILES_TO_MONITOR,
            storage_paths_to_monitor=STORAGE_PATHS_TO_MONITOR
        )
        # Emit stats to all connected clients
        socketio.emit('update_stats', current_stats)
        # print(f"Stats emitted at {current_stats['timestamp']}") # Uncomment for verbose logging
        count += 1
        
        # Determine polling interval from environment variable (in milliseconds)
        polling_interval_ms_str = os.environ.get('POLLING_INTERVAL_MS', '2000')
        try:
            polling_interval_s = int(polling_interval_ms_str) / 1000.0
            # Enforce a minimum polling interval to prevent excessive load
            if polling_interval_s < 0.5: 
                polling_interval_s = 0.5 
        except ValueError:
            polling_interval_s = 2.0 # Default if POLLING_INTERVAL_MS is not a valid integer
        
        socketio.sleep(polling_interval_s) # Use socketio.sleep for cooperative multitasking with eventlet

# Flask route for the main page
@app.route('/')
def index():
    """Serves the main HTML page."""
    # Pass the polling interval to the template for potential use (e.g. chart data points)
    polling_interval_ms_str = os.environ.get('POLLING_INTERVAL_MS', '2000')
    try:
        polling_interval_ms = int(polling_interval_ms_str)
        if polling_interval_ms < 500: polling_interval_ms = 500 # Ensure a minimum for frontend too
    except ValueError:
        polling_interval_ms = 2000 
    return render_template('index.html', polling_interval_ms=polling_interval_ms)

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    print(f'Client connected: {request.sid}') 
    # Start the background thread only once using a Flask app context global
    # This ensures the thread isn't restarted on every new connection if it's already running.
    if not hasattr(app, 'stats_thread_started_flag') or not app.stats_thread_started_flag:
        socketio.start_background_task(target=background_thread)
        app.stats_thread_started_flag = True 
        print("Background stats emitter thread started.")
    else:
        print("Background stats emitter thread already running.")
    
    # Send initial full data dump to the newly connected client
    initial_stats = get_all_stats(
        log_files_to_monitor=LOG_FILES_TO_MONITOR,
        storage_paths_to_monitor=STORAGE_PATHS_TO_MONITOR
    )
    emit('update_stats', initial_stats) # Emit only to the connecting client

@socketio.on('disconnect')
def handle_disconnect():
    """Handles client disconnections."""
    print(f'Client disconnected: {request.sid}')

# The `if __name__ == '__main__':` block for `socketio.run(app, ...)`
# is now in `run.py`, which is the entrypoint specified in the Dockerfile's CMD.
