#!/usr/bin/env python
"""
MAIN LAUNCHER - This must be the first file that runs
"""
import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# MUST BE ABSOLUTELY FIRST - before ANY other imports
import eventlet
eventlet.monkey_patch()

# Now import and run the app
from app import app, socketio

if __name__ == '__main__':
    print("Starting application with proper eventlet monkey patching...")
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        allow_unsafe_werkzeug=True
    )