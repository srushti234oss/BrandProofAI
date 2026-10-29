# BrandProof

BrandProof is a full-stack, human-led brand content review workspace. The React/TypeScript frontend uses a Django REST Framework API and Django ORM persistence. It supports accounts, workspace roles, brand rules and guideline versions, approved evidence, content uploads, claim triage, terminology checks, advisory visual checks, corrections, exact-version reviews, comments, audit history, clarity signals and printable Trust Receipts.

## Local setup

Requirements: Python 3.10+, Node.js 20+, and (for OCR) Tesseract OCR. SQLite is the local default; PostgreSQL is supported with `DATABASE_URL`.

1. Copy `.env.example` to `backend/.env`; replace `DJANGO_SECRET_KEY` with a random secret. Leave `DATABASE_URL` unset for SQLite, or set it to a PostgreSQL connection URL.
2. From `backend/`, create and activate a virtual environment, then run `pip install -r requirements.txt`.
3. Apply migrations with `python3 manage.py migrate`, then create an account through the web UI (or run `python3 manage.py createsuperuser`).
4. Start the API with `python3 manage.py runserver`.
5. In a second backend terminal, start the durable analysis worker with `python3 manage.py run_analysis_worker`. Use `--once` to process one queued job.
6. In another terminal, run `cd frontend && npm install && npm run dev`; open http://localhost:5173.
7. Register, create a workspace, add brand rules and approved evidence, and submit text or a supported file. Analysis jobs remain visibly queued if the worker is stopped.

## Hackathon deployment (Render)

The default `render.yaml` is a temporary single-origin demo deployment. It builds the React app into Django and runs Gunicorn plus the analysis worker in one service with SQLite on ephemeral storage. `render.persistent.yaml` is a separate opt-in durable profile with paid web/worker services, a dedicated PostgreSQL database, and private S3-compatible uploads. Both profiles use Django migrations only: **they do not run `seed_demo` or create sample workspace/content records**. After deploy, register your own account, create your workspace, and enter your own guidelines, evidence, and review content.

1. Put this project in a GitHub repository. Do not upload `.env`, `backend/.env`, `backend/db.sqlite3`, or uploaded files. The `.gitignore` excludes these local/private files and generated dependency/build folders.
2. In Render, choose **New → Blueprint**, connect the repository, and create the Blueprint from `render.yaml`. Render generates the Django secret. No AI key or new PostgreSQL database is required to start the deployment.
3. Wait for the `brandproof` service to finish building, then open its `onrender.com` URL. Register, create a workspace, add at least one rule and an approved evidence source, and submit your own pasted copy. The worker processes submissions. Do not run `seed_demo` for a clean project.
4. To enable LLM analysis, create a Groq API key, then open the service's **Environment** settings in Render and add it as `LLM_API_KEY`. The Blueprint sets `LLM_BASE_URL` and `LLM_MODEL` to Groq's OpenAI-compatible endpoint and `openai/gpt-oss-20b`. Save and deploy. Keep the key in Render's secret settings, never in GitHub or chat. With no LLM key, deterministic rules still run, while factual claims remain unverified. Groq free-tier requests are subject to rate limits; if you reach one, the app keeps its rule checks and reports the provider warning.
5. Tesseract OCR is included in this deployment image, so image and scanned-PDF OCR can run without a separate OCR API key.

**Temporary demo storage warning:** SQLite and uploaded files are on Render's temporary local filesystem. User accounts, workspaces, reviews, and uploads can disappear when the service restarts, sleeps, or redeploys. This is only for a short-lived demonstration. Do not enter sensitive content. For persistence, deploy the optional `render.persistent.yaml` architecture only after reviewing provider costs and supplying isolated private object-storage credentials; do not reuse another app's database without isolating it.

### Persistent Round 3 Render profile

`render.persistent.yaml` is the opt-in durable architecture profile. It creates a paid Render web service, a separate paid analysis worker, and a dedicated managed PostgreSQL database. The database is separate from any other app database. Both services share the database and private S3-compatible file storage. The web service applies migrations at startup; the worker processes the shared database queue and reclaims stale jobs. Do not create this Blueprint until the team leader reviews Render's current service/database charges and the selected storage provider's charges.

To configure it, use **New → Blueprint** and choose `render.persistent.yaml`. On creation, supply an isolated private S3-compatible bucket name, region, and access credentials in Render's secret fields (for Cloudflare R2, also supply its S3 endpoint). Supply the Groq key only if using AI. Never put secrets in the repository or chat. Create the services, wait for web/worker/database to become healthy, then run one new account/workspace journey and upload a private file. Verify the file can be downloaded only by workspace members and still exists after redeploy. The new web URL replaces the current demo URL only after those checks pass. The profile starts with a clean database; it does not migrate accounts or content from the existing ephemeral demo.

The PostgreSQL migration enables pgvector and creates an HNSW cosine index when the database role allows extension creation. The configured embedding provider must support `/embeddings` and return 1536 dimensions for database-side ranking; otherwise the app uses its tested JSON/lexical fallbacks. Configure a backup/restore procedure and monitor Render service, worker and database health before describing the deployment as production-ready. Render-managed database backups depend on the selected plan. This profile improves durability and worker isolation but is not a high-availability architecture.
For an explicitly labeled walkthrough workspace, run from `backend/`:

```sh
python3 manage.py seed_demo --username brandproof-demo --password 'choose-a-demo-password'
```

The walkthrough uses the same deterministic rule and review models. It labels seeded records `DEMO`; it does not represent real evidence or an executed LLM call. The command reports the username but never prints the password.

For structured claim and tone analysis, set `LLM_API_KEY`, `LLM_MODEL`, and optionally `LLM_BASE_URL` in the backend environment. For embedding retrieval, also set `LLM_EMBEDDING_MODEL` to a compatible embedding model. Submitted extracted text and only retrieved, approved workspace evidence passages are sent to that configured provider; the UI discloses this. Without a configured provider, terminology/rule checks run locally and claim candidates remain unverified. Do not use production confidential content until you have configured an appropriate provider and private file storage.

For PostgreSQL, install dependencies, create a database and set `DATABASE_URL`, then apply the same migrations. In production set `DJANGO_DEBUG=false`, a strong secret, explicit `DJANGO_ALLOWED_HOSTS`, HTTPS and trusted origins. Configure private object storage and retention controls before accepting sensitive uploads; local media files are not publicly routed by this application.

For private S3-compatible file storage, install the backend requirements and set `DJANGO_STORAGE_BACKEND=s3`, `AWS_STORAGE_BUCKET_NAME`, and the region/endpoint values in `backend/.env`. Provide credentials through the hosting platform's secret manager (or the standard AWS credential chain); do not commit them. Configure the bucket to block public access and grant the application only the required object permissions. BrandProof downloads files through a workspace-authenticated endpoint. For invitation email, configure the `EMAIL_*` values and `DEFAULT_FROM_EMAIL`; set `PUBLIC_APP_URL` to the public frontend address. Put SMTP passwords in the hosting secret manager. Without SMTP, invitations still work through the manual one-time link.

## Product workflows

- **Guidelines:** create guidelines from pasted text, TXT, PDF or DOCX; edit guideline source/name; create, edit, enable/disable and delete structured rules; version history is recorded. PDF text carries `[Page N]` markers. Extraction warnings block false success.
- **Evidence:** maintain approved internal passages or upload evidence TXT/PDF/DOCX. Approved/disallowed examples can be configured on each guideline. A workspace-scoped retriever selects only approved passages. When `LLM_EMBEDDING_MODEL` is configured, it stores embeddings and uses a PostgreSQL pgvector HNSW cosine index for compatible 1536-dimension vectors; SQLite, unsupported dimensions or an unavailable pgvector index use cosine ranking from JSON vectors, then lexical ranking when vectors are unavailable. Sources remain attached to claims. Referenced evidence cannot be hard-deleted; approval can be revoked to exclude it from future runs while preserving prior citations.
- **Content:** submit pasted content, TXT, PDF, DOCX, PNG or JPEG up to 20 MB. Original files are retained in Django storage. Extraction method/status/warnings are retained per version. Tesseract OCR is optional. Scanned PDF pages use optional PyMuPDF rendering plus Tesseract OCR when installed; page and word-region confidence metadata is retained where OCR succeeds.
- **Analysis:** configured deterministic terminology and absolute-claim checks run locally. Without an LLM, factual-looking claims are marked unverified, never contradicted merely for lack of evidence. With an LLM, response structure and returned workspace source/rule IDs are validated. Provider errors become warnings and do not imply compliance.
- **Visual checks:** image palette summaries compare dominant colors with configured colors and are advisory. Logo checks use scale-limited OpenCV grayscale template matching and return confidence/region information. Both require configured reference data. When high-confidence OCR boxes exist, contrast is estimated from local luminance percentiles and flagged as advisory; it is not an accessibility certification. OCR requires a working local Tesseract installation.
- **Review:** findings support comments/replies, status history and dismissal reasons. Reviewer/manager/admin roles can decide reviews; managers can assign findings to workspace reviewers; approvals with unresolved findings require a recorded override reason. Every approval belongs to one content version. Corrections save new versions and trigger reanalysis. Suggested phrases replace only their matched passage; full-content deterministic drafts are applied as full content. Workspace members can download retained source files through an authenticated, workspace-scoped endpoint. The original upload remains retained, and a text correction to an uploaded asset is not overwritten by re-extracting its original file.
- **Receipts and clarity:** receipts read persisted version hashes, findings, checked sources and review decisions and can be printed/saved as PDF in the browser. Clarity candidates require at least three recorded dismissals, requested changes or comments; accepting or editing a rewrite creates a new guideline version; suggestions can also be rejected. The simple signal model is not AI disagreement analysis.
- **Campaign consistency:** compares readable latest versions of assets sharing the same campaign name. It flags repeated sentence patterns with changed numbers, variants of configured preferred wording, and recognized disclaimer markers that appear in some but not all assets. It is deliberately conservative: disclosure rules vary by format, and possible mismatches ask a person to verify instead of deciding truth or legal compliance.
- **API:** endpoints live under `/api/v1/`; generated OpenAPI schema is at `/api/schema/`. Authentication uses Django sessions and CSRF protection. Per-user and anonymous throttles are enabled. List endpoints accept optional `page` and `page_size` parameters while retaining the existing array response when pagination is not requested.

## Verification

From `backend/`:

```sh
python3 manage.py test app
python3 manage.py check
python3 manage.py makemigrations --check --dry-run
```

From `frontend/`:

```sh
npm run build
```

The deploy container itself could not be built locally unless Docker Desktop is installed and running. Render builds the same Dockerfile during deployment and reports any container-build errors in its deploy log.

The synthetic labelled cases in `backend/app/evaluation_cases.json` cover evidence classifications, terminology, tone and visual scenarios. The test suite exercises workspace isolation, claim source validation, rule checks, lexical and vector evidence retrieval, extraction metadata, visual advisory/logo matching, uploaded-asset corrections, permissions, comments, version-specific approval, Trust Receipts, clarity thresholds, queue retries, invitations, pagination, retention and demo seeding. No accuracy or real-world evaluation percentages are claimed.

## Retention, invitations and operations

- Workspace admins can set `retention_days` in Settings. Run `python3 manage.py purge_expired_assets --dry-run` to inspect due deletions, then schedule `python3 manage.py purge_expired_assets` with a trusted system scheduler to enforce the policy. Asset deletion removes original files and cascaded review data while writing an audit event.
- Workspace admins can create single-use, seven-day invitation links for an email and role. When SMTP is configured, BrandProof emails the invitation; otherwise it displays the link for manual sharing. Invited users accept it during registration.
- Run the database-backed analysis worker as a separate process. Jobs persist queued/processing/completed/warnings/failed states, stale processing jobs are reclaimed, and `--max-attempts 3` retries failed analysis up to three times with backoff. A final failed run can still be retried from the asset review.

## Remaining limitations

- Database-side vector ranking requires PostgreSQL, the `vector` extension, provider vectors with 1536 dimensions, and configured `LLM_EMBEDDING_MODEL` support for the compatible `/embeddings` endpoint. Other local/provider configurations use the tested JSON cosine and lexical fallbacks. Existing JSON embeddings are mirrored into the index as they are used by analysis; no vector is fabricated when the provider does not return one.
- Contrast estimates and logo checks are heuristic and remain advisory: generic image analysis cannot reliably determine which colors are intentional brand elements or prove a logo is authentic. OCR regions can be incomplete or wrong. Contrast is not an accessibility certification. Improve confidence with a workspace-specific labelled image set and human review; do not treat these checks as automatic compliance decisions.
- Private source-file downloads, configurable SMTP invitation delivery, and configurable private S3-compatible storage are implemented. They still require SMTP/storage settings and production credentials. Local development defaults to private Django media files. Production backups, monitoring, HTTPS, and scheduling the documented retention command must be configured on the chosen host. The separate Render persistent profile uses PostgreSQL, private object storage, and an isolated worker; it is not high availability and still needs owner-configured backups, monitoring, credentials, and restore verification.
- The frontend remains a single-page React workspace and the backend uses one Django app. This is an organizational choice in this MVP, not a disconnected feature; splitting it into multiple packages is a maintainability refactor and does not add user-facing capability.
- External AI, embeddings, database, OCR binaries, SMTP, object storage and deployment availability are configuration dependencies. Live provider and hosted-infrastructure behavior must be checked after the owner configures those services; automated tests do not claim real-world model or visual accuracy.
