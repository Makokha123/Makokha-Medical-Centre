import multiprocessing
import os

# This app uses standard Flask request handling (no Socket.IO worker required).
# Prefer threaded workers for better concurrency on I/O-bound endpoints.
worker_class = os.getenv('GUNICORN_WORKER_CLASS', 'gthread')

# Default worker count: keep conservative unless explicitly configured.
workers = int(os.getenv('WEB_CONCURRENCY', '1'))

# Threads are used by the gthread worker class.
threads = int(os.getenv('GUNICORN_THREADS', '4'))

# Bind to the port provided by the platform (Render sets PORT)
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# (worker_connections is not used by gthread/sync workers; left unset intentionally.)

# Graceful timeout settings
timeout = int(os.getenv('TIMEOUT', '60'))
graceful_timeout = int(os.getenv('GRACEFUL_TIMEOUT', '30'))

# Logging
accesslog = '-'  # stdout
errorlog = '-'   # stderr
loglevel = os.getenv('LOG_LEVEL', 'info')

# Ensure the app object import path is correct
wsgi_app = 'app:app'

# Preload can reduce memory usage, but keep off by default for safety.
preload_app = os.getenv('PRELOAD_APP', '').strip().lower() in ('1', 'true', 'yes', 'y', 'on')
