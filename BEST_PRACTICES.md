# 📘 Project Best Practices

## 1. Project Purpose
A clinical management web application built with Flask. It supports multi-role workflows (admin, doctor, pharmacist, receptionist), including patient records, prescriptions/dispensing, inventory, billing/sales/refunds, money management, bed/ward tracking, backup/disaster recovery, and limited AI-assisted clinical documentation (DeepSeek/OpenAI).

## 2. Project Structure
- app.py: Single-file Flask application containing app initialization, routes, and SQLAlchemy models. Also registers the auth blueprint.
- config.py: Central configuration (environment-driven), encryption setup (Fernet), mail, DeepSeek config, and helpers for encrypt/decrypt.
- templates/: Jinja2 templates organized by role and feature.
  - admin/: dashboards, drugs, dosage, beds, employees, reports, transactions, medical_tests, money, backups, disaster recovery.
  - doctor/: patient workflows (new, active, old, details, medical record), layout, dashboard.
  - pharmacist/: inventory, dispensing, sales, receipts, refunds.
  - receptionist/: billing and dashboard.
  - auth/: login and password reset templates.
  - base.html, profile.html, errors/.
- static/: Static assets.
  - css/, js/ (main.js, dashboard.js, sw.js), images/, icons/, manifest.json, uploads/.
- utils/: Internal helpers (encryption utilities).
- instance/: SQLite database (clinic.db) for local/dev.
- requirements.txt: Python dependencies.
- .env: Environment variables (not committed).

Recommended evolution
- Break out modules:
  - app_factory.py (create_app), models/, services/, blueprints/ (auth, admin, doctor, pharmacist, receptionist, api), tasks/ (APScheduler jobs), emails/, forms/, schemas/.
  - tests/ folder (see Test Strategy).
- Use application factory + init_app for extensions (db, migrate, login, csrf, limiter, mail) and blueprint registration.

## 3. Test Strategy
Current state
- No tests folder or framework detected.

Recommendation
- Framework: pytest with pytest-flask and coverage.
- Structure:
  - tests/
    - conftest.py (app, client, db fixtures via create_app testing config + in-memory SQLite)
    - unit/ (models, utils)
    - integration/ (routes, DB interactions)
    - e2e/ (role-based flows with login)
- Naming: test_<module>.py and descriptive test function names.
- Mocking: use unittest.mock/pytest-mock for external services (mail, S3, AI APIs, APScheduler jobs).
- Data: factory_boy / pytest fixtures for Users, Patients, Drugs, etc.
- Coverage: target ≥80% lines/branches on critical paths (auth, billing, inventory, money, patient workflows).
- What to test:
  - Unit: model properties (hybrid props), helpers (number generators), encryption utilities, permission checks.
  - Integration: each route’s auth/role guard, form validation, JSON endpoints (success/error), DB side-effects.
  - Security: CSRF on forms, rate limits for sensitive endpoints, login/logout, password reset token validity/expiry.
  - Regression: money management AJAX flows: /admin/money/summary, /admin/check_pending_payments, form POSTs (update_bill, update_purchase, etc.).

## 4. Code Style
Python/Flask
- Use application factory pattern and init_app for extensions (db, migrate, login_manager, csrf, limiter, mail). Avoid global state where possible.
- Datetime: prefer timezone-aware UTC consistently: datetime.now(timezone.utc). Avoid mixing with datetime.utcnow.
- SQLAlchemy:
  - Keep models in dedicated files with __tablename__, created_at/updated_at defaults, and helper methods.
  - Use session.add + commit; wrap in try/except with rollback and structured logging. Avoid calling db.create_all() at request time.
  - Avoid deprecated engine.execute raw SQL; prefer ORM/SQLAlchemy Core with text() only when necessary.
- Security:
  - Use Werkzeug’s generate_password_hash/check_password_hash for User passwords (consistent hashing). Avoid storing plaintext.
  - Ensure CSRFProtect is initialized on the app (csrf.init_app(app)) and templates include CSRF tokens for forms.
  - Use Flask-Limiter for sensitive endpoints (password reset, login, AI calls).
  - Encrypt PII consistently using Config.encrypt_data/Config.decrypt_data for fields like name, address, phone, NOK details; maintain key rotation strategy.
- Errors/Logging:
  - Centralize error handling with errorhandlers and structured logs (include user_id, ip, action). Use AuditLog for CRUD trails where applicable.
  - Return JSON with shape {success: bool, error?: str, data?: any} for AJAX endpoints.
- Naming:
  - snake_case for functions/variables; PascalCase for class names; CONSTANTS_UPPER.
  - Templates: use meaningful names by role and feature (already followed).
- Comments/Docs:
  - Docstrings for models, services, complex routes; inline comments for non-obvious logic.
  - Keep route functions small; move business logic into services.
- Frontend (templates/JS):
  - Use unobtrusive JS, event delegation, and module-like objects (e.g., window.moneyManagement). Keep IDs/classes stable and documented.
  - Maintain accessibility (aria-*), semantic HTML, consistent BEM-like CSS naming.

## 5. Common Patterns
- Role-based routing: /admin, /doctor, /pharmacist, /receptionist guarded by @login_required and role checks.
- Jinja templating per role; base.html for shared layout.
- AJAX JSON APIs for dashboard/money summaries and actions; forms often submit via fetch and expect JSON {success|error}.
- DataTables used in admin money page; initialize with responsive, paging, scrollX.
- Money formatting: Ksh with thousands separators and 2 decimals.
- Identifiers: helper generators (generate_sale_number, generate_bulk_sale_number, generate_individual_sale_number, generate_patient_number, generate_* numbers for entities).
- Auditing: AuditLog for actions; recommend using consistently on create/update/delete.
- Encryption: Config.init_fernet(app) at startup; utils/encryption provides class-based helper with current_app logging.
- Background jobs: APScheduler (background scheduler) for backups/maintenance (ensure safe initialization under app context).
- AI integration: AIService uses DeepSeek/OpenAI with retries and fallbacks; ensure strict timeouts, error logging, and role-limited access.

## 6. Do's and Don'ts
Do
- Enforce role checks at route entry. Redirect unauthorized users with flash messages.
- Validate and sanitize all form inputs. Use Flask-WTF where possible and include CSRF tokens.
- Use UTC-aware datetimes consistently and store in DB as UTC.
- Wrap DB writes in try/except; rollback on exceptions; log with context.
- Return consistent JSON contracts for frontend AJAX: {success: true, data} or {success: false, error}.
- Keep templates free of heavy logic; move to view functions/services.
- Keep encryption/decryption centralized via Config or utils.EncryptionUtils; never hardcode keys.
- Paginate and index DB queries for dashboards; avoid N+1 queries.
- Keep static assets versioned or cache-busted; maintain service worker with clear caching strategy.

Don't
- Don’t mix hashing libraries for passwords; prefer Werkzeug consistently.
- Don’t perform db.create_all() at request time; migrations should manage schema (Flask-Migrate/Alembic).
- Don’t return raw exceptions to clients; log server-side and return safe messages.
- Don’t block request threads with long-running tasks (backups, emails); use background threads/queues.
- Don’t expose sensitive settings in templates or JS; use environment variables.
- Don’t assume naive datetimes; avoid utcnow() mixed with timezone-aware code.

## 7. Tools & Dependencies
Key libraries
- Flask: web framework, routing, Jinja2 templating.
- Flask-Login: session management and user authentication.
- Flask-WTF/WTForms: form handling and CSRF protection.
- Flask-Migrate/SQLAlchemy/Alembic: ORM and migrations.
- Flask-Mail: email sending (password reset).
- Flask-Limiter: rate limiting.
- APScheduler: background/scheduled jobs.
- cryptography.Fernet: encryption of PII.
- boto3: S3 storage for backups (optional).
- httpx/requests: HTTP clients.
- openai: AI client; DeepSeek via OpenAI client with custom base_url.
- DataTables/jQuery (frontend): tables and AJAX interactions.

Setup
- Python >=3.10 recommended.
- Create and activate virtualenv, then install dependencies:
  - pip install -r requirements.txt
- Environment (.env) keys (example):
  - FLASK_ENV=development
  - SECRET_KEY=...
  - SECURITY_PASSWORD_SALT=...
  - DATABASE_URL=sqlite:///clinic.db (or your RDBMS URL)
  - FERNET_KEY=44-char-urlsafe-base64
  - MAIL_SERVER=smtp-relay.brevo.com (or smtp.gmail.com)
  - MAIL_PORT=587
  - MAIL_USE_TLS=true
  - MAIL_USERNAME=...
  - MAIL_PASSWORD=...
  - MAIL_DEFAULT_SENDER=no-reply@yourdomain.com
  - DEEPSEEK_API_KEY=...
  - DEEPSEEK_BASE_URL=https://api.deepseek.com (if needed)
  - DEEPSEEK_TIMEOUT=30
  - BREVO_EMAIL=... (if using Brevo)
  - BREVO_SMTP_KEY=...
  - BACKUP_FOLDER=backups
  - UPLOAD_FOLDER=uploads
- DB migrations (recommended):
  - flask db init (first time)
  - flask db migrate -m "message"
  - flask db upgrade

## 8. Other Notes
For LLM code generation
- Preserve route shapes and return types. AJAX handlers should return JSON with success/error keys used by frontend code (e.g., moneyManagement).
- Respect UI conventions in templates/admin/money.html:
  - Forms use IDs ending with -form; modal IDs map to -modal; events are delegated via data-* attributes.
  - Endpoints like /admin/money/summary and /admin/check_pending_payments return specific numeric/aggregate data.
  - DataTables initialization expects <table> within .table-responsive containers.
  - Currency: use "Ksh" format with 2 decimals and thousands separators.
- Maintain role-based authorization: only admins for money, inventory, backups; doctors for clinical workflows; pharmacists for dispensing/sales; receptionists for billing.
- Add csrf.init_app(app) in the application factory; include CSRF tokens in all forms and AJAX (X-CSRFToken header) if CSRF is enabled.
- Use consistent UTC datetimes (datetime.now(timezone.utc)) for created_at/updated_at.
- Centralize business logic in services and reuse helpers (ID generators, audit logging, encryption, email).
- When adding new features:
  - Add tests (unit + integration) and update templates/JS accordingly.
  - Update Alembic migrations for schema changes.
  - Wire into dashboards and role menus consistently.
