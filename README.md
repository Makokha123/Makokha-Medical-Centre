Makokha Medical Centre - Local Run Instructions

SocketIO run instructions:

1. Activate your venv (example PowerShell):

   & 'c:\\Users\\User\\Desktop\\Makokha Medical Centre\\MMC\\Scripts\\Activate.ps1'

2. Install requirements (ensure Flask-SocketIO and eventlet):

   pip install -r requirements.txt
   pip install eventlet

3. Run with SocketIO server:

   python run_socketio.py

This will start the server on http://localhost:5000 and enable real-time messaging via Socket.IO.

Notes:
- In production, use eventlet or gevent and a proper message queue (Redis) for scaling Socket.IO.
- Ensure SECRET_KEY and DATABASE_URL are set in environment for production.
