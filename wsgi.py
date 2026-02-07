import os

# Ensure Flask-SocketIO uses eventlet when this entrypoint is used.
os.environ.setdefault('SOCKETIO_ASYNC_MODE', 'eventlet')

try:
    import eventlet
    eventlet.monkey_patch()
except Exception:
    # If eventlet fails to patch for any reason, continue.
    # (Gunicorn worker class / async mode should be adjusted accordingly.)
    eventlet = None

from app import app, socketio

# Flask-SocketIO installs a WSGI middleware into app.wsgi_app, so exporting the
# Flask app itself is the correct WSGI callable for Gunicorn.
application = app

# Backward-compatible alias for existing Render start commands.
socketio_app = app

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)