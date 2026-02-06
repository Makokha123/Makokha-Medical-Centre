import eventlet
eventlet.monkey_patch()

import socketio as socketio_pkg

from app import app, socketio

# Create the WSGI app for Gunicorn
socketio_app = socketio_pkg.WSGIApp(socketio.server, app)

# This is what Gunicorn will use
application = socketio_app

if __name__ == "__main__":
    import os
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)