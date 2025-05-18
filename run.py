# /app/run.py (This file should be at the root of your app context in the Docker image)

# Perform monkey patching as the VERY first thing
import eventlet
eventlet.monkey_patch()

# Now import other necessary modules
import os
from backend.app import app, socketio # Import your Flask app and SocketIO instances

if __name__ == '__main__':
    print("Starting Flask-SocketIO server via run.py (monkey-patched)...")
    
    # Get host and port from environment variables or use defaults
    # FLASK_RUN_HOST is set in the Dockerfile
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0') 
    # FLASK_RUN_PORT is set in the Dockerfile
    port = int(os.environ.get('FLASK_RUN_PORT', '5000')) 
    
    # FLASK_DEBUG can be set as an ENV in Dockerfile or docker run for debug mode
    # Example: ENV FLASK_DEBUG=1 for development, ENV FLASK_DEBUG=0 for production
    # The default in the Dockerfile is 0 (production)
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    
    # use_reloader=False is generally recommended for production or when using external process managers.
    # Eventlet itself handles some aspects of reloading if debug is True, but explicit False is safer here.
    # For development, if FLASK_DEBUG=1, the reloader might be active depending on Flask/Eventlet versions.
    # For production (FLASK_DEBUG=0), use_reloader should definitely be False.
    socketio.run(app, host=host, port=port, debug=debug_mode, use_reloader=False)
