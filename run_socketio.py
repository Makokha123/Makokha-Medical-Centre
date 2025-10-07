#!/usr/bin/env python
"""
SocketIO Runner - Fixed version
"""
import os
import sys

# Add current directory to path first
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import sys

# If a debugger is attached (for example VS Code debugpy), creating or
# monkey-patching eventlet can cause greenlet/thread mismatches because the
# debugger may spawn threads before eventlet gets a chance to patch. Detect
# that case and fall back to the threading async mode which is safe for the
# debugger. In normal runs, apply eventlet monkey patching first and use it.
debugger_attached = sys.gettrace() is not None or 'debugpy' in sys.modules

# Allow forcing async mode via environment variable for debugging/CI needs.
# Valid values: 'eventlet', 'threading'. When not set, we auto-detect.
forced_mode = os.environ.get('SOCKETIO_ASYNC_MODE')
if forced_mode:
    forced_mode = forced_mode.lower()

if debugger_attached:
    print("Debugger detected -> running Socket.IO with threading async mode (no eventlet monkey patch).")
    # Import here after deciding not to monkey patch.
    from app import app
    # Create a SocketIO instance configured for threading mode so it doesn't
    # rely on eventlet/gevent greenlets. We avoid using the socketio instance
    # that may have been created in app (so we create a local one here).
    from flask_socketio import SocketIO
    socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

    def _run_threading(port=5000):
        print(f"Starting SocketIO server (threading mode) on port {port}...")
        # Try binding to 0.0.0.0 first; if that fails try 127.0.0.1.
        for host in ('0.0.0.0', '127.0.0.1'):
            try:
                socketio.run(app, host=host, port=port, debug=False, use_reloader=False)
                return
            except PermissionError as e:
                print(f"PermissionError binding to {host}:{port}: {e}")
            except OSError as e:
                print(f"OSError binding to {host}:{port}: {e}")
        # If we reach here, binding failed for both hosts on this port
        raise PermissionError(f"Failed to bind to port {port} on both 0.0.0.0 and 127.0.0.1")

    if __name__ == '__main__':
        # Try a series of ports and hosts until one succeeds. Allow override
        # of the primary port via SOCKETIO_PORT env var for debugging.
        env_port = os.environ.get('SOCKETIO_PORT')
        candidate_ports = ()
        if env_port:
            try:
                candidate_ports = (int(env_port), 5000, 5001, 8000)
            except Exception:
                candidate_ports = (5000, 5001, 8000)
        else:
            candidate_ports = (5000, 5001, 8000)

        for p in candidate_ports:
            try:
                _run_threading(p)
                break
            except PermissionError:
                print(f"Could not bind to port {p}; trying next port...")
        else:
            print("Unable to bind any candidate ports (5000,5001,8000). This may be due to another process using the ports or OS firewall/policy blocking bindings (WinError 10013). Try:")
            print(" - Run VS Code / the terminal as Administrator, or")
            print(" - Choose a different port and set SOCKETIO_PORT env var, or")
            print(" - Stop any process currently using these ports (check with 'Get-NetTCPConnection -LocalPort <port>').")
            sys.exit(1)
else:
    # Normal execution path: patch early, then import the app so SocketIO can
    # detect and use eventlet properly.
    # If an env var forces threading, skip eventlet path.
    if forced_mode == 'threading':
        print("Environment forces threading mode for Socket.IO")
        from app import app
        from flask_socketio import SocketIO
        socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')
        if __name__ == '__main__':
            try:
                socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)
            except PermissionError:
                print('PermissionError binding port 5000 in forced threading mode')
                raise
    else:
        # Normal execution path: patch early, then import the app so SocketIO can
        # detect and use eventlet properly. Ensure monkey_patch runs before
        # importing app modules that may create threads/locks.
        import eventlet
        eventlet.monkey_patch()

        print("Eventlet monkey patch applied successfully")

        # Now import the app (this import will pick up the environment we've
        # prepared by monkey-patching)
        from app import socketio, app

        def _run_eventlet(port=5000):
            print(f"Starting SocketIO server (eventlet mode) on port {port}...")
            try:
                socketio.run(
                    app,
                    host='0.0.0.0',
                    port=port,
                    debug=True,
                    use_reloader=False,
                    allow_unsafe_werkzeug=True,
                )
            except OSError as e:
                # Windows may raise PermissionError/WinError 10013 when port
                # is reserved or access is denied. Surface a helpful message.
                print(f"OSError while binding port {port}: {e}")
                raise

        if __name__ == '__main__':
            try:
                _run_eventlet(5000)
            except OSError:
                print("Port 5000 blocked, trying port 5001 for eventlet...")
                _run_eventlet(5001)