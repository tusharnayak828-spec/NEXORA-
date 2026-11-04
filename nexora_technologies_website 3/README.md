# Nexora Professional Demo Suite

A responsive, browser-based portfolio suite containing three interactive B2B concept demos.

## Included
1. **FactoryOS** — manufacturing work-order register, production status, progress, stage mix, add work order, CSV export.
2. **ClientFlow CRM** — B2B lead list, pipeline value, stage updates, add lead, CSV export.
3. **DocuMind AI** — document intake/review workflow, sample extraction simulation, approval queue, CSV export.

## Run locally
Open `index.html` in a modern browser. No build step or API keys are required.

## Data and privacy
- Sample data is fictional.
- Changes are stored in the browser's localStorage on the current device/browser.
- Do not upload confidential or real customer documents.
- This is a front-end demo, not a production deployment.

## Honest capability notes
- FactoryOS and ClientFlow CRM demonstrate local browser interactions only; no multi-user backend, authentication, role permissions, or live ERP/CRM integrations.
- DocuMind AI simulates extraction. It does not run OCR, call an LLM, or send files to a server.
- Production implementation should add authenticated APIs, PostgreSQL, audit logs, file storage, validation, access controls, backups, monitoring, and integrations.
- Use fictional/demo data in public presentations. Do not describe these concepts as completed client deployments.

## Suggested production architecture
- Frontend: React / Next.js
- API: Python Flask or FastAPI
- Database: PostgreSQL
- Authentication: secure sessions + role-based access
- Document pipeline: private object storage + OCR + LLM extraction + deterministic validation + human approval
- Hosting: Render or equivalent, with managed PostgreSQL and backups
