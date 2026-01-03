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
    print("Starting application on port", port)
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
    )