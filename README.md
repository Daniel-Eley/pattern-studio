# Pattern Studio

A Django + React application that turns plain-language descriptions into regular expressions, previews replacements, and exports cleaned CSV or Excel data.

**Submission status:** Source and deployment configuration are included. A public deployment, live LLM verification, and recorded demo still need to be completed. No public URL or video is claimed yet.

## Features

- Upload UTF-8 CSV, XLSX, or XLS; view data in pages of 100 rows.
- Describe a pattern (for example, “Find email addresses in the Email column”).
- Generate a structured regex plan with the OpenAI Responses API; view the regex, explanation, match count, and before/after cells.
- Override the target column, supply a literal replacement, or leave it blank to remove matches.
- Apply only after preview, reset to the original data, and download CSV or XLSX.
- Session-scoped datasets, CSRF protection, bounded file parsing, regex execution deadlines, and formula-safe exports.
- Clearly labelled offline sample mode for email, phone, and URL presets. **Sample mode does not satisfy the LLM requirement.**

## Local setup

Prerequisites: Python 3.11–3.13 and Node.js 22 or later.

From the repository root, in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
.venv\Scripts\python manage.py migrate
cd frontend
npm ci
npm run build
cd ..
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

Open http://127.0.0.1:8000. On macOS/Linux, use `.venv/bin/python` in place of `.venv\Scripts\python` and `cp .env.example .env`.

For frontend hot reload, run `npm run dev` from `frontend/` in a second terminal, keeping Django running on port 8000. Vite proxies `/api` to Django. Open the URL printed by Vite.

### Enable the real LLM

Set these values in the root `.env` file and restart Django:

```dotenv
OPENAI_API_KEY=your-own-key
OPENAI_MODEL=gpt-4o-mini
DEMO_MODE=0
```

The key is used only by Django. Never commit it or expose it through a frontend environment variable. An API account with model access and available credit is required; a chat subscription alone is not API configuration. The model can be changed to another model supporting structured Responses output.

Only the user's description and column names are sent to the model. Spreadsheet cell values are not sent. Descriptions and headers may themselves contain private information. Generated regex is validated and executed locally on the server. Responses are requested with `store=False`; provider retention rules still apply.

The integration follows [OpenAI structured outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Architecture

```text
React + Vite → same-origin Django JSON API → service layer
                                            ├─ bounded CSV / Excel parsing
                                            ├─ OpenAI structured pattern plan
                                            ├─ regex validation + timed replacement
                                            └─ PostgreSQL (production) / SQLite (local)
```

`Dataset` stores original/current rows and a monotonically increasing version. `Operation` stores a preview plan and its source version. Applying a stale or already-applied plan returns 409, preventing an accidental second replacement. Applying changes never requires another LLM call.

The React build is served by Django/WhiteNoise in production. A multistage Docker build compiles React and packages the Python service, so the browser and API share one origin and CSRF protection works without permissive CORS.

## API

All mutations require the session cookie and `X-CSRFToken` header. Initialize both with `GET /api/bootstrap/`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health/` | Health check |
| POST | `/api/datasets/` | Multipart `file` upload |
| GET | `/api/datasets/{id}/?page=1` | Paginated current data |
| POST | `/api/datasets/{id}/preview/` | JSON description, replacement, optional columns list |
| POST | `/api/datasets/{id}/apply/{operation_id}/` | Apply stored preview |
| POST | `/api/datasets/{id}/reset/` | Restore original rows |
| POST | `/api/datasets/{id}/delete/` | Remove dataset and operations |
| GET | `/api/datasets/{id}/download/?format=csv` | Export CSV or XLSX |

Example preview body:

```json
{"description":"Find email addresses in the Email column","replacement":"REDACTED","columns":["Email"]}
```

Errors are returned as `{"error":"…"}` for input validation. Unauthorized dataset access is 404. Expired previews are 409. Framework CSRF failures are 403 and the frontend supplies a readable fallback message.

## Tests

```powershell
.venv\Scripts\python manage.py test
cd frontend
npm run build
```

Tests cover the assignment's email example, preview/apply/reset/export, session isolation, CSRF, stale/repeated operations, malformed uploads, XLSX types, literal replacements, formula protection, regex timeout, and the LLM adapter with a mocked provider. The mock verifies the adapter contract but does not prove live model accuracy. Before submission, test real LLM requests for emails, phone numbers, URLs, postal codes, and invoice identifiers, including no-match cases.

## Deployment on Render

`Dockerfile` and `render.yaml` define a web service and PostgreSQL database. Review current plan availability and any costs shown by Render before completing account setup. The free database may have a limited lifetime; choose a suitable plan for the review period.

1. Create or sign into GitHub, create a `pattern-studio` repository, and push this source. Do not upload `.env`, `.venv`, or database files.
2. Create or sign into Render and connect GitHub.
3. Choose **New → Blueprint**, select the repository, and use its `render.yaml`.
4. Supply `OPENAI_API_KEY`. The blueprint generates `SECRET_KEY` and connects `DATABASE_URL`. Keep `DEMO_MODE=0` for the final submission.
5. Deploy. The container builds React, collects static assets, runs database migrations, and starts Gunicorn. Render supplies the hostname, which Django adds to its allowed hosts.
6. Open the resulting HTTPS URL. Test upload → real LLM preview → apply → download in a new browser session, plus reset and invalid input.
7. Record the verified public URL here and in the internship submission.

See [Render's Django deployment guide](https://render.com/docs/deploy-django) and [Docker deployment documentation](https://render.com/docs/docker).

For another container host, set `SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS`, `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, and `DEMO_MODE=0`. The service must sit behind a trusted HTTPS proxy that sets `X-Forwarded-Proto`; never expose the application directly with untrusted forwarded headers.

## Demo video

The recording has not been made yet. Use [the 90-second demo script](docs/demo-script.md). After recording, upload the MP4 through GitHub's README editor to get a GitHub-hosted video attachment, then replace this paragraph with its URL. GitHub renders supported uploaded video attachment URLs as an inline player. A relative MP4 link alone is not a reliable inline embed.

## Limits and tradeoffs

- This is a synchronous internship-scale app: 5 MB uploads, 10,000 rows, 100 columns, 100,000 cells, and 10,000 characters per source text cell. XLSX expansion is limited to 30 MB. Larger workloads need streamed ingestion, background jobs, and object storage.
- Only the first Excel worksheet is imported. Formatting, formulas as executable formulas, workbook structure, and macros are not preserved. XLSX formulas are treated as text; legacy XLS reads cached cell values. Excel dates become ISO strings. Numeric and null Excel cells are not modified; CSV cells remain strings, preserving leading zeroes.
- Only string cells are transformed. Replacement text is literal: `$1` and `\1` are not capture references. Context-dependent zero-width matches can occur; patterns matching the empty input are rejected.
- Exports prefix formula-like strings with an apostrophe to prevent spreadsheet formula execution. This is an intentional change to exported literal values, including headers.
- Preview displays up to six changed cells; the API returns at most 100 examples. Counts and apply cover the entire dataset.
- Workspace access expires after 24 hours. Data is not automatically deleted at the instant access expires. Schedule `python manage.py cleanup_data` hourly on your host to delete expired datasets, and `python manage.py clearsessions` daily for session records. Cleanup also runs on container startup.
- Limits are per session (10 uploads and 30 successful previews/hour), not abuse-proof global rate limiting. Before promoting beyond a reviewer demo, add authenticated accounts, edge rate limiting, a provider spending limit, scheduled cleanup, and monitoring. Failed LLM requests do not consume the preview quota.
- Regex generation is probabilistic; review the pattern and preview. Email and phone matching are practical patterns, not complete standards validators.
- Optional extra LLM transformations and large-file support are intentionally outside the initial scope.

## Submission checklist

- [ ] GitHub repository published and accessible to reviewers
- [ ] Production LLM key configured and live requests verified
- [ ] Public URL tested end to end
- [ ] Demo video recorded and embedded above
- [ ] Explain the design, limitations, and tests confidently in the interview
