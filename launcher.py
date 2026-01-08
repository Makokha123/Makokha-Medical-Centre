#!/usr/bin/env python
"""
MAIN LAUNCHER - This must be the first file that runs
"""
import os
import sys

# Add the current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import the Flask app
from app import app

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() in ['true', '1', 't']
    print(f"Starting application on port {port} with debug mode {'on' if debug_mode else 'off'}")
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
    )