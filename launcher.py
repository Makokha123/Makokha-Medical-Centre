#!/usr/bin/env python
"""
MAIN LAUNCHER - This must be the first file that runs
"""
import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import the Flask app and SocketIO instance without side effects so that
# process managers (e.g., Gunicorn) can import this module safely.
from app import app, socketio

if __name__ == '__main__':
    # Only apply eventlet monkey patching when running this script directly.
    # Do NOT monkey patch at import time to avoid breaking Gunicorn's master.
    import eventlet
    eventlet.monkey_patch()

    port = int(os.getenv('PORT', '5000'))
    print("Starting application (eventlet) on port", port)
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=True,
        allow_unsafe_werkzeug=True,
    )