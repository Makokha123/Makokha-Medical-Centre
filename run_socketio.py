#!/usr/bin/env python
"""
SocketIO Runner - Fixed version
"""
import os
import sys

# Add current directory to path first
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# ABSOLUTELY FIRST - before any imports
import eventlet
eventlet.monkey_patch()

print("Eventlet monkey patch applied successfully")

# Now import the app
from app import socketio, app

if __name__ == '__main__':
    print("Starting SocketIO server...")
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=True,
        allow_unsafe_werkzeug=True
    )