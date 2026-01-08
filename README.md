Makokha Medical Centre - Local Run Instructions

1. Activate your venv (example PowerShell):

   & 'c:\\Users\\makok\\Desktop\\Makokha-Medical-Centre\\venv\\Scripts\\Activate.ps1'

2. Install requirements:

   pip install -r requirements.txt

3. Set required environment variables (recommended via a local .env file):

   - Copy `.env.example` to `.env` and fill in values (do not commit `.env`).

   - SECRET_KEY
   - SECURITY_PASSWORD_SALT
   - FERNET_KEY
   - BACKUP_ENCRYPTION_KEY
   - DATABASE_URL (optional for local; defaults to SQLite in instance/)

4. Run locally:

   python launcher.py

Production notes:
- Use Gunicorn with [gunicorn.conf.py](gunicorn.conf.py) (threaded workers by default).
- Configure Redis (REDIS_URL) for rate limiting storage if running multiple workers.
- Do not ship default credentials; user seeding is disabled unless explicitly enabled via env.

Optional one-time seeding (local/dev only):
- Set `SEED_DEFAULT_USERS=true` and provide `SEED_ADMIN_EMAIL` + `SEED_ADMIN_PASSWORD` (and optionally `SEED_ADMIN_USERNAME`).
