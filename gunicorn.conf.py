import multiprocessing
import os

# Worker class must match the async framework used by Flask-SocketIO
# Eventlet is installed, so use the eventlet worker to avoid blocking calls in the main loop.
worker_class = 'eventlet'

# Number of workers: for Socket.IO eventlet, a small number is typical.
workers = int(os.getenv('WEB_CONCURRENCY', '1'))

# Bind to the port provided by the platform (Render sets PORT)
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Increase worker connections for WebSocket/long polling
worker_connections = int(os.getenv('WORKER_CONNECTIONS', '1000'))

# Graceful timeout settings
timeout = int(os.getenv('TIMEOUT', '60'))
graceful_timeout = int(os.getenv('GRACEFUL_TIMEOUT', '30'))

# Logging
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = os.getenv('LOG_LEVEL', 'info')

# Ensure the app object import path is correct
wsgi_app = 'app:app'

# Preload disabled for eventlet + Flask-SocketIO to avoid monkey-patch issues
preload_app = False
