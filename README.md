# BrandProof

**BrandProof is a human-led brand governance workspace for reviewing promotional content.** It checks submitted campaign copy and creative files against workspace-specific guidelines, structured rules, and approved evidence. It brings the findings, source references, reviewer decisions, corrections, and version history together so a person can make and document the final decision.

> BrandProof is a decision-support tool. An AI result, rule match, visual check, or campaign comparison is not legal advice, proof of truth, or an automatic compliance approval. Reviewers remain responsible for decisions.

## What you can do

- Create an account, create or switch workspaces, rename a workspace, and manage member roles (admin, manager, reviewer, creator).
- Invite teammates with role-specific, single-use links; send invitations by email when SMTP is configured or share the manual link.
- See the animated BrandProof introduction before sign-in and a sidebar-linked feature walkthrough after entering a workspace; the walkthrough can be skipped.
- Use the branded glass-effect interface, responsive workspace navigation, and dashboard for review activity and open findings.
- Add brand guidelines from pasted text or TXT, PDF, and DOCX files; edit and version them.
- Turn guideline requirements into structured prohibited-term, preferred-term, tone, claim, and general rules; enable, disable, edit, or delete rules.
- Add approved and disallowed examples, evidence sources, brand colors, and reference logos. Approve or revoke evidence for analysis.
- Submit pasted campaign copy or TXT, PDF, DOCX, PNG, and JPEG assets (up to 20 MB); retain source files and extraction status with the asset version.
- Analyze content with deterministic rules and, when configured, a Gemini or other supported OpenAI-compatible language-model endpoint. Claims without sufficient approved evidence are kept unverified; the system does not treat missing evidence as proof that a claim is false.
- Inspect findings, matched rules, and source references; search and filter findings; assign work, comment, change finding status, and record review decisions.
- Draft a correction, compare versions, and preserve the original. Applying a correction creates a new version and a fresh analysis/review.
- Generate a printable Trust Receipt for the selected content version, its findings, evidence, and review decisions.
- Compare the latest readable assets with the same campaign name for repeated numeric claims, configured preferred wording, and recognized disclosure-marker differences.
- Review guideline-clarity candidates derived from recorded reviewer feedback; accepting a rewrite or editing it creates a guideline version.
- Run optional image checks: OCR, palette summaries, approximate logo-template matching, and advisory contrast estimates.
- Configure optional asset retention; purge expired assets with the management command.

## Architecture

BrandProof is a single-page React application served by Django. In production the frontend and API share one origin, which keeps session authentication and CSRF handling straightforward.

```text
Browser
  └── React + TypeScript (Vite build)
        ├── Django-served static frontend
        └── /api/v1/*  Django REST Framework
                         ├── Django ORM ── SQLite (local/demo) or PostgreSQL
                         ├── Analysis queue ── Django worker
                         ├── File storage ── private local media or S3-compatible bucket
                         ├── Gemini / OpenAI-compatible API (optional)
                         ├── Embeddings + lexical retrieval (optional hybrid retrieval)
                         └── Tesseract / OpenCV visual checks (optional/runtime-dependent)
```

### Main components and data flow

1. A signed-in member submits copy or a file to a workspace. The API verifies membership and permissions, stores the asset and its version, and records extraction metadata.
2. Text is taken from pasted copy or extracted from TXT, PDF, DOCX, or OCR-supported images/scanned PDF pages. Extraction warnings are kept with the version.
3. Deterministic rules inspect the extracted text. Approved evidence and relevant guideline material are retrieved within the same workspace. When an LLM is configured, only the analysis context needed for that run is sent to the configured provider; the result is validated and attached to findings. Provider errors produce a warning and preserve deterministic findings.
4. Analysis is represented by a persisted job/run. The included worker processes queued jobs, retries failures, and recovers stale processing jobs. The temporary Render blueprint runs the worker alongside the web process; the persistent profile runs it as a separate service.
5. Findings, comments, status changes, decisions, corrections, audit records, and version hashes are stored through Django ORM. A correction creates another version; it does not overwrite the reviewed original.

### Technology

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| Backend/API | Python, Django, Django REST Framework |
| Database | Django ORM; SQLite for local and temporary demo use; PostgreSQL for durable deployments |
| Vector retrieval | PostgreSQL `pgvector` with HNSW cosine index when available and compatible 1536-dimension vectors are configured; JSON cosine and lexical fallbacks otherwise |
| AI provider | Gemini through its OpenAI-compatible API or another compatible endpoint, configured by environment variables; AI is optional |
| Document/image processing | TXT/PDF/DOCX extraction, Tesseract OCR, optional PyMuPDF PDF page rendering, OpenCV logo-template matching |
| Production packaging | Multi-stage Docker build; Gunicorn; Render Blueprint examples |
| File storage | Private Django media in local/demo mode; optional private S3-compatible object storage in persistent deployments |

## Repository map

```text
backend/
  app/                  Models, API views, analysis, retrieval, extraction, tests
  config/               Django settings, root URLs, WSGI/ASGI configuration
  manage.py             Django management entry point
  requirements.txt      Backend dependencies
frontend/
  src/main.tsx          React application and screens
  src/style.css         Product styling and motion
  vite.config.ts        Local development server/proxy
  package.json          Frontend dependencies and scripts
deploy/
  render-start.sh       Migrate, start worker, then start web process
  render-web-start.sh   Persistent-profile web startup
Dockerfile              Builds frontend and Django container
render.yaml             Temporary single-service Render demo profile
render.persistent.yaml  Optional PostgreSQL + separate worker + private storage profile
.env.example            Local configuration template
```

The backend's principal records include workspaces and memberships, guidelines and versions, rules and examples, assets and versions, findings, reviews, comments and audit events, evidence sources and references, extracted claims, embeddings, correction suggestions, palette entries, reference logos, analysis runs, and guideline-clarity insights. See `backend/app/models.py` for the current schema.

## Local development

### Prerequisites

- Python 3.10 or newer
- Node.js 20 or newer
- Tesseract OCR for OCR features (other core text and review workflows can run without it)
- PostgreSQL only if you want to develop against PostgreSQL; SQLite is the local default

### Start the application

1. Copy `.env.example` to `backend/.env`. For local development, keep `DATABASE_URL` unset to use SQLite. Set a private `DJANGO_SECRET_KEY`; never use the sample value in production.
2. Install backend dependencies and migrate:

   ```sh
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python3 manage.py migrate
   ```

3. Start Django in the `backend/` directory:

   ```sh
   python3 manage.py runserver
   ```

4. In a second terminal, start the analysis worker from `backend/`:

   ```sh
   source .venv/bin/activate
   python3 manage.py run_analysis_worker
   ```

   `--once` processes one available job and exits. If the worker is not running, queued analyses remain queued until a worker processes them.

5. In a third terminal, start Vite:

   ```sh
   cd frontend
   npm install
   npm run dev
   ```

6. Open <http://localhost:5173>, register, create a workspace, add a guideline/rule and approved evidence, then submit content for review. Vite proxies API requests to the local Django service. Set `VITE_API_URL` only when intentionally pointing the frontend at a different API origin.

For an administrator account, run `python3 manage.py createsuperuser` from `backend/`. Django admin is available at `/admin/`.

## Configuration

The backend reads environment variables (including `backend/.env` for local development). Render and other hosts should use their secret/environment settings rather than committed files.

| Variable | Purpose |
| --- | --- |
| `DJANGO_SECRET_KEY` | Django signing secret. Use a long, private random value. |
| `DJANGO_DEBUG` | Debug mode; must be `false` in production. |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames accepted by Django. |
| `DATABASE_URL` | Optional database URL. Unset uses local SQLite; configure PostgreSQL for durable shared data. |
| `CORS_ALLOWED_ORIGINS` | Allowed browser origins when frontend and API are on separate origins. |
| `CSRF_TRUSTED_ORIGINS` | Trusted origins for Django CSRF protection, including the deployed HTTPS site. |
| `VITE_API_URL` | Optional frontend API origin. Normally blank for Vite proxy/local and same-origin deployment. |
| `LLM_API_KEY` | Secret key for the configured LLM provider. Never commit or share it. |
| `LLM_BASE_URL` | OpenAI-compatible API base URL. See Gemini setup below. |
| `LLM_MODEL` | Model identifier accepted by the selected provider. |
| `LLM_EMBEDDING_MODEL` | Optional compatible embedding model for semantic evidence retrieval. |
| `DEMO_USERNAME`, `DEMO_PASSWORD` | Optional public judge-demo login display. Use a dedicated demo account only. |
| `DJANGO_STORAGE_BACKEND` | `local` for local/private media or `s3` for configured S3-compatible storage. |
| `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_S3_ENDPOINT_URL` | Private object-storage settings; endpoint is needed for compatible non-AWS services. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Object-storage credentials. Store only in the host's secret manager. |
| `AWS_S3_SERVER_SIDE_ENCRYPTION`, `AWS_QUERYSTRING_EXPIRE` | Optional upload encryption and signed-download expiry settings. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Optional SMTP invitation delivery. Store the password as a secret. |
| `EMAIL_USE_TLS`, `EMAIL_USE_SSL`, `DEFAULT_FROM_EMAIL` | SMTP transport and sender configuration. |
| `PUBLIC_APP_URL` | Public application URL used to create invitation links. |

### Configure Gemini

The provider is selected by the endpoint, model name, and API key; the Render Blueprint's defaults are **Groq**, so they must be changed if using Gemini. In the web service's environment settings set:

```text
LLM_API_KEY=<your Gemini API key>
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=<a model enabled for your Gemini API key>
```

Use the model identifier shown as available to your key in Google's Gemini API documentation/console. Save the variables and restart or redeploy the service so the running process reads them. Never put the key in frontend code, GitHub, screenshots, or chat. If the key is missing, invalid, rate-limited, or the provider is unavailable, local deterministic checks remain available and the review should show an AI/provider warning; do not interpret that as a successful AI analysis.

For another OpenAI-compatible provider, use its documented API base URL, valid model identifier, and key. Embeddings are a separate optional capability: configure `LLM_EMBEDDING_MODEL` only when the selected provider supports the compatible embeddings endpoint and the expected dimensions.

## API overview

The API root is `/api/v1/`. The interactive schema is at `/api/schema/`. Authentication uses Django session cookies and CSRF protection; APIs enforce workspace membership and role permissions. Throttling is enabled. List endpoints support optional `page` and `page_size` query parameters and preserve the array response when pagination is not requested.

| Route group | What it covers |
| --- | --- |
| `auth/`, `auth/logout/` | Session status, sign-in/sign-out, and account access |
| `workspaces/` | Workspace listing/creation, settings/rename, dashboard, members, roles, and invitations |
| `workspaces/{id}/guidelines/`, `rules/`, `examples/` | Guideline versions, structured rules, and examples |
| `workspaces/{id}/evidence/`, `claims/` | Approved evidence, claim ledger, and claim adjudication |
| `workspaces/{id}/palette/`, `logos/` | Brand color and reference-logo configuration |
| `workspaces/{id}/assets/`, `versions/` | Submission, asset versions, source files, and analysis retry |
| `workspaces/{id}/findings/`, `review/`, `corrections/`, `receipt/` | Findings, comments/status actions, decisions, corrections, and Trust Receipts |
| `workspaces/{id}/history/`, `audit/` | Review and audit history |
| `workspaces/{id}/clarity/`, `campaigns/consistency/` | Guideline-clarity insights and cross-asset campaign comparison |
| `workspaces/{id}/integrations/` | Runtime integration/configuration status |

The exact route definitions are in `backend/app/urls.py`; permission and request details are in `backend/app/views.py` and the schema endpoint.

## Optional demo workspace and judge credentials

The normal deployment starts without sample workspace or review records. Create an account and enter real project-specific demo content, or explicitly seed a clearly labelled walkthrough workspace from `backend/`:

```sh
python3 manage.py seed_demo --username brandproof-demo --password 'choose-a-demo-password'
```

The seeder creates records labelled `DEMO`; sample claims/evidence are illustrative and are not real verification. For a public judge login, set `DEMO_USERNAME` and `DEMO_PASSWORD` in the host settings to the credentials of that dedicated account, then run the seeder against the same deployed database using the same username/password. These credentials are intentionally displayed to every visitor, so never reuse a personal password or account. The seeder does not overwrite an existing demo workspace.

## Deployment

### Temporary Render demo

`render.yaml` creates a single-origin Docker web service. It builds the frontend into Django, runs migrations, Gunicorn, and the analysis worker in the same service. It uses SQLite and local uploaded-file storage on Render's temporary filesystem. This is suitable for a short-lived demo only: records and uploaded files can be lost after a restart, sleep, or redeploy. Do not submit sensitive content. Configure Gemini as described above if AI analysis is needed; the Blueprint initially specifies Groq values.

### Persistent Render profile

`render.persistent.yaml` is a separate optional architecture: paid web and worker services, an isolated managed PostgreSQL database, and private S3-compatible file storage. It applies migrations at web startup and runs analysis in a separate worker. Before creating it, review current Render and storage-provider costs. Supply a private bucket, region/endpoint and credentials in Render's secret settings. The profile starts with a clean database; it does not copy data from the temporary demo. Configure and verify backups, restore, HTTPS, monitoring, retention scheduling, and service health before treating the deployment as production-ready. It improves persistence and process isolation, but is not high availability.

To enable private S3-compatible storage, set `DJANGO_STORAGE_BACKEND=s3`, bucket, region/endpoint and credentials. Block public bucket access and grant only the required object permissions. Downloads go through workspace-authenticated endpoints. To send invitations by email, configure SMTP variables; without SMTP the app provides a manual single-use invitation link.

For any production deployment: use a strong secret, `DJANGO_DEBUG=false`, explicit allowed hosts and HTTPS trusted origins; keep provider/database/storage/SMTP credentials in the hosting platform's secret manager. A deployment's environment values—not local `.env` values—control its running configuration.

## Analysis, retrieval, and visual-check behavior

- Deterministic rule checks run locally. LLM analysis is optional and can add claim/tone assessment and correction suggestions. Model output is validated; provider failures are warnings, not approvals.
- A potential factual claim with no relevant approved evidence remains unverified and needs a person to review it. Only workspace-approved sources are eligible for retrieval. Source references are retained with findings; revoking approval excludes a source from future analysis while preserving earlier records.
- Evidence retrieval combines lexical relevance with embeddings when available. PostgreSQL can use pgvector/HNSW for compatible 1536-dimension vectors. If PostgreSQL, extension permissions, provider embeddings, or compatible dimensions are unavailable, the application falls back to JSON-vector cosine and/or lexical ranking. No embeddings are fabricated.
- OCR may extract text from images and rendered PDF pages when Tesseract (and for PDF rendering, PyMuPDF) are available. Poor images, scans, or unsupported file contents can produce incomplete extraction and warnings.
- Palette, approximate logo-template matching, and contrast estimation are heuristics. Contrast is advisory and not an accessibility certification; logo matching does not prove authenticity. Configure reference colors/logos and have a person verify results.
- Campaign consistency compares readable latest versions grouped under the same campaign name. It flags possible differences for human verification; it does not determine which offer is correct, legal, or compliant.
- `retention_days` is a policy setting; enforcement requires scheduling `purge_expired_assets` on a trusted host. Local demo storage and temporary Render storage are not durable backups.

## Operations and maintenance commands

Run these from `backend/` with the virtual environment active:

```sh
python3 manage.py migrate
python3 manage.py check
python3 manage.py run_analysis_worker --poll-seconds 2 --stale-minutes 10 --max-attempts 3
python3 manage.py purge_expired_assets --dry-run
```

After reviewing the dry run, schedule `python3 manage.py purge_expired_assets` with an appropriate scheduler if retention enforcement is required. The worker stores job states, retries failures with backoff, and reclaims stale work; a final failed analysis can be retried from the asset review.

## Verification commands

The repository includes backend tests and a frontend production build command. Run these when making changes:

```sh
# From backend/
python3 manage.py test app
python3 manage.py check
python3 manage.py makemigrations --check --dry-run

# From frontend/
npm run build
```

The labelled synthetic cases in `backend/app/evaluation_cases.json` cover evidence classifications, terminology, tone, and visual scenarios. The automated suite covers workspace isolation, permissions, analysis/retrieval, extraction metadata, visual checks, corrections, version-specific approvals, receipts, clarity thresholds, queue retries, invitations, pagination, retention, and demo seeding. These are test fixtures and coverage areas, not a claim of real-world accuracy or a verified hosted-provider evaluation. Live Gemini/other-provider, Render, database, OCR-binary, and object-storage behavior depends on the configured services.

## Known limitations

- The temporary Render deployment uses ephemeral local data and file storage. Use the persistent profile and verify backup/restore for data that must survive deploys.
- pgvector retrieval needs PostgreSQL, the `vector` extension, compatible 1536-dimension vectors, and a working embedding endpoint. JSON-vector and lexical fallbacks preserve retrieval when those requirements are absent, but do not provide database-side indexing.
- AI output can be unavailable, rate-limited, malformed, or wrong. Deterministic findings remain available where possible; human review is required, especially for factual and regulatory claims.
- OCR and visual checks can miss or misread content; they are advisory. No automated visual result proves brand compliance or logo authenticity.
- Email, private object storage, backups, monitoring, HTTPS, and scheduled retention are optional operational integrations and need owner-provided services and credentials.
- The product is organized as one React application and one Django app. Further modularization or a dedicated job broker would be future engineering work, not an existing capability.

## Roadmap

Potential next steps after the current implementation are production-grade background-job infrastructure and observability; stronger, workspace-calibrated visual evaluation with labelled human-reviewed examples; and richer operational reporting and export/integration workflows. Prioritize them against user feedback and measured failure cases. Do not describe a roadmap item as implemented until it has shipped and been verified.
