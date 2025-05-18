# backend/app.py

from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import eventlet # Required for async mode with Flask-SocketIO
# Corrected import: Use relative import for modules within the same package
from .collectors import get_all_stats 
import os
# It's good practice to import request from flask for socketio events if you need request context
from flask import request 

# Use eventlet for asynchronous operations
eventlet.monkey_patch()

app = Flask(__name__, template_folder='../frontend', static_folder='../frontend/static')
app.config['SECRET_KEY'] = os.urandom(24) # Secret key for session management
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*") # Allow all origins for simplicity

# --- Configuration for monitored items ---
# Define storage paths to monitor. These are paths INSIDE the container.
# Mount host paths to these container paths using Docker's -v option.
# Example: -v /data:/mnt/host_data
STORAGE_PATHS_TO_MONITOR = ['/'] # Default to root. Add more like '/mnt/host_data'
if 'STORAGE_PATHS' in os.environ:
    # If STORAGE_PATHS is set, split it by comma and use those paths
    # Example: STORAGE_PATHS="/,/mnt/data1,/mnt/data2"
    STORAGE_PATHS_TO_MONITOR = [path.strip() for path in os.environ['STORAGE_PATHS'].split(',') if path.strip()]
    if not STORAGE_PATHS_TO_MONITOR: # Handle empty string case
        STORAGE_PATHS_TO_MONITOR = ['/'] # Fallback to default if parsing results in empty list
        print("Warning: STORAGE_PATHS environment variable was empty or invalid. Defaulting to ['/'].")
elif os.path.exists('/host_root'): # Check if a common mount point for host root exists
    STORAGE_PATHS_TO_MONITOR = ['/host_root'] # If so, default to monitoring it

print(f"Monitoring storage paths: {STORAGE_PATHS_TO_MONITOR}")


# Define log files to monitor. These are paths INSIDE the container.
# Mount host log files to these paths.
# Example for LOG_CONFIG env var: "Syslog:/mnt/logs/syslog.log,Auth Log:/mnt/logs/auth.log"
LOG_FILES_TO_MONITOR = [
    {'name': 'Container Dummy Log 1', 'path': '/app/dummy_log1.log'},
    {'name': 'Container Dummy Log 2', 'path': '/app/dummy_log2.log'}
]
if 'LOG_CONFIG' in os.environ:
    user_logs_config = []
    try:
        # Split by comma for multiple log configs
        configs_str = os.environ['LOG_CONFIG'].split(',')
        for config_item_str in configs_str:
            if ':' not in config_item_str: # Basic validation for "Name:Path" format
                print(f"Warning: Skipping invalid LOG_CONFIG item '{config_item_str}'. Expected format 'Name:Path'.")
                continue
            name, path = config_item_str.split(':', 1) # Split only on the first colon
            user_logs_config.append({'name': name.strip(), 'path': path.strip()})
        
        if user_logs_config: # If any valid user logs were parsed
            LOG_FILES_TO_MONITOR = user_logs_config
            print(f"Using user-defined log files: {LOG_FILES_TO_MONITOR}")
        else:
            print("Warning: LOG_CONFIG was set but no valid configurations found. Using default dummy logs.")
            # Keep default dummy logs if LOG_CONFIG is invalid or results in an empty list
    except Exception as e: # Catch any parsing errors
        print(f"Warning: Error parsing LOG_CONFIG environment variable: {e}. Using default dummy logs.")
        # Keep default dummy logs on error

# Create dummy log files for demonstration if they are in the active config and don't exist
# In a real scenario, these would be actual log files you mount into the container.
for log_conf in LOG_FILES_TO_MONITOR:
    if 'dummy_log' in log_conf['path'].lower() and not os.path.exists(log_conf['path']):
        try:
            with open(log_conf['path'], 'w') as f:
                f.write(f"Dummy log '{log_conf['name']}' started for JS monitor at {time.strftime('%Y-%m-%d %H:%M:%S')}.\n")
            print(f"Created dummy log: {log_conf['path']}")
        except Exception as e:
            print(f"Error creating dummy log {log_conf['path']}: {e}")


# Background thread to periodically send updates
def background_thread():
    """Periodically fetches stats and emits them via WebSocket."""
    print("Starting background stats emitter...")
    count = 0
    while True:
        # Simulate log activity for dummy logs if they are part of the active configuration
        for log_conf in LOG_FILES_TO_MONITOR:
            if 'dummy_log' in log_conf['path'].lower() and os.path.exists(log_conf['path']):
                try:
                    with open(log_conf['path'], 'a') as f:
                        f.write(f"Log entry {count} at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    # Limit dummy log size
                    if os.path.getsize(log_conf['path']) > 1024 * 10: # 10KB limit per dummy log
                        with open(log_conf['path'], 'r+') as f:
                            lines = f.readlines()
                            f.seek(0); f.truncate()
                            f.writelines(lines[-100:]) # Keep last 100 lines
                except Exception as e:
                    print(f"Error writing to or trimming dummy log {log_conf['path']}: {e}")
        
        current_stats = get_all_stats(
            log_files_to_monitor=LOG_FILES_TO_MONITOR,
            storage_paths_to_monitor=STORAGE_PATHS_TO_MONITOR
        )
        socketio.emit('update_stats', current_stats)
        # print(f"Stats emitted at {current_stats['timestamp']}") # Can be verbose, uncomment for debugging
        count += 1
        
        # Get polling interval from environment variable, default to 2 seconds
        polling_interval_ms_str = os.environ.get('POLLING_INTERVAL_MS', '2000')
        try:
            polling_interval_s = int(polling_interval_ms_str) / 1000.0
            if polling_interval_s < 0.5: # Enforce a minimum polling interval (e.g., 0.5 seconds)
                polling_interval_s = 0.5 
        except ValueError:
            polling_interval_s = 2.0 # Default if POLLING_INTERVAL_MS is not a valid integer
        
        socketio.sleep(polling_interval_s)


@app.route('/')
def index():
    """Serves the main HTML page."""
    # Pass the polling interval to the template for potential use (e.g. chart data points)
    polling_interval_ms_str = os.environ.get('POLLING_INTERVAL_MS', '2000')
    try:
        polling_interval_ms = int(polling_interval_ms_str)
        if polling_interval_ms < 500: polling_interval_ms = 500 # Ensure a minimum for frontend too
    except ValueError:
        polling_interval_ms = 2000 # Default if invalid
    return render_template('index.html', polling_interval_ms=polling_interval_ms)

@socketio.on('connect')
def handle_connect():
    """Handles new client connections."""
    print(f'Client connected: {request.sid}') # Log client session ID
    # Start the background thread only once using a Flask app context global
    # This ensures the thread isn't restarted on every new connection if it's already running.
    if not hasattr(app, 'stats_thread_started_flag') or not app.stats_thread_started_flag:
        socketio.start_background_task(target=background_thread)
        app.stats_thread_started_flag = True # Set flag to indicate thread has been started
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
    print(f'Client disconnected: {request.sid}') # Log client session ID


if __name__ == '__main__':
    # This block is for local development.
    # The Dockerfile uses `flask run` which should pick up eventlet due to monkey_patch.
    # For more robust production, consider `gunicorn -k eventlet -w 1 backend.app:app`
    print("Starting Flask-SocketIO development server on http://0.0.0.0:5000")
    # You can set environment variables for local testing if needed:
    # os.environ['POLLING_INTERVAL_MS'] = '1000' 
    # os.environ['STORAGE_PATHS'] = '/,./test_mount' # Example for local testing
    # os.environ['LOG_CONFIG'] = "TestLog1:./test_log1.log,TestLog2:./test_log2.log"
    # if not os.path.exists('./test_mount'): os.makedirs('./test_mount')
    # if not os.path.exists('./test_log1.log'): open('./test_log1.log', 'w').write('Test log 1 started.\n')
    # if not os.path.exists('./test_log2.log'): open('./test_log2.log', 'w').write('Test log 2 started.\n')

    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
