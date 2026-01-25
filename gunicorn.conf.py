# Gunicorn configuration for Simonini-isms
import os

# Server socket
bind = "0.0.0.0:5000"

# Worker processes
workers = int(os.getenv('WORKERS', '2'))
worker_class = "sync"
worker_connections = 1000
timeout = 120
keepalive = 2

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Process naming
proc_name = "simonini-isms"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (handled by nginx)
keyfile = None
certfile = None
