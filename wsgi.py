import os

# IMPORTANT:
# Do not force Eventlet in production by default.
# Render/Gunicorn can crash if `os` gets monkey-patched in the master process:
#   RuntimeError: do not call blocking functions from the mainloop
#
# If you explicitly want Eventlet, set `SOCKETIO_ASYNC_MODE=eventlet`.
#
# IMPORTANT (Render/Gunicorn): if your start command uses `gunicorn -k eventlet ...`,
# eventlet's worker will attempt to monkey-patch. If we don't patch *before* importing
# Flask/Werkzeug/SQLAlchemy, eventlet may try to upgrade already-created objects and
# trigger context errors like:
#   RuntimeError: Working outside of application/request context.
_socketio_async_mode = (os.getenv('SOCKETIO_ASYNC_MODE') or '').strip().lower()
_gunicorn_cmd = (os.getenv('GUNICORN_CMD_ARGS') or '').lower()
_using_gunicorn_eventlet = ('-k eventlet' in _gunicorn_cmd) or ('--worker-class eventlet' in _gunicorn_cmd) or ('worker_class=eventlet' in _gunicorn_cmd)

if _socketio_async_mode == 'eventlet' or _using_gunicorn_eventlet:
    try:
        import eventlet
        # Avoid patching `os` so Gunicorn arbiter pipes don't become green.
        eventlet.monkey_patch(os=False)
    except Exception:
        pass

from app import app, socketio

# Flask-SocketIO installs a WSGI middleware into app.wsgi_app, so exporting the
# Flask app itself is the correct WSGI callable for Gunicorn.
application = app

# Backward-compatible alias for existing Render start commands.
socketio_app = app

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 10000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)