# Nexora Technologies — website

Flask website for Nexora Technologies with responsive marketing pages, project enquiry capture, SQLite lead storage and a password-protected admin dashboard.

## Routes
- / — company website and enquiry form
- /privacy and /terms — draft legal pages; review before publishing
- /admin/login — administrator sign-in
- /admin — private enquiry dashboard

## Render setup
Build: `pip install -r requirements.txt`
Start: `gunicorn app:app`
Required environment variables: `SECRET_KEY`, `CONTACT_EMAIL` (replace placeholder with a verified inbox), `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `COOKIE_SECURE=true`.

## Important
This repository is public. Never commit credentials, API keys, customer information or .env files. Demo concepts are illustrative, not client case studies. Nexora is a proposed business brand; verify legal status and contact details before publication.

**Storage warning:** this deployment uses SQLite on a free Render service, whose local filesystem is ephemeral. Leads can be lost on restarts or redeploys. Before collecting real customer enquiries, connect durable managed PostgreSQL or a suitable persistent disk and update the application/database configuration. Legal pages are draft templates, not legal advice.