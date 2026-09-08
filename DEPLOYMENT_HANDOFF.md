# Fleet Rebalancer Deployment Handoff

Last updated: 2026-09-08

## Current checkpoint

The project is being prepared for a persistent deployment on an Oracle Cloud Always Free ARM VM. The frontend and API are deployed together behind one public HTTPS origin using Docker Compose and Caddy.

Do not commit credentials. Keep `.env` local and configure production secrets only on the Oracle VM.

## Completed

- Audited the repository for secrets, generated artifacts, and unwanted AI-authorship markers.
- Added `psycopg[binary]==3.2.9` to `requirements.txt` and `environment.yml`.
- Added `SUPABASE_DB_URL` to `.env.example` and typed settings.
- Replaced the API's production checkpoint selection with `PostgresSaver` when `SUPABASE_DB_URL` is present.
- Retained `InMemorySaver` as a local fallback when no database URL is configured.
- Verified Supabase connectivity through the Session pooler.
- Verified LangGraph tables exist: `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, and `checkpoint_migrations`.
- Added browser-specific `X-Session-ID` workflow routing for tick, status, approve, and reject requests.
- Added API `/health` endpoints.
- Enabled Next.js standalone output.
- Added Oracle deployment packaging:
  - `Dockerfile.api`
  - `Dockerfile.web`
  - `docker-compose.yml`
  - `Caddyfile`
  - `.dockerignore`
- Confirmed the tracked XGBoost model is included in the API image.

## Validation completed

- Python tests: `58 passed`.
- Backend Ruff checks: passed.
- Python compilation: passed.
- Next.js production standalone build: passed.
- Modified Python files: no editor diagnostics.
- PostgresSaver initialization: passed.
- Supabase checkpoint schema: verified.
- Docker validation: not yet run because Docker was unavailable before the computer restart.

## Current uncommitted changes

Expected modified files include:

- `.env.example`
- `api/_shared.py`
- `api/approve.py`
- `api/index.py`
- `api/reject.py`
- `api/status.py`
- `api/tick.py`
- `environment.yml`
- `requirements.txt`
- `scripts/local_server.py`
- `src/rebalancer/config.py`
- `web/next.config.ts`
- `web/src/components/SystemSelector.tsx`
- `web/src/lib/api.ts`

Expected new files:

- `.dockerignore`
- `Caddyfile`
- `Dockerfile.api`
- `Dockerfile.web`
- `docker-compose.yml`
- `DEPLOYMENT_HANDOFF.md`

## Immediate next action

After Docker Desktop is running, open a new PowerShell or Anaconda Prompt and execute from the repository root:

```powershell
docker version
docker compose version
docker compose config
docker buildx build --platform linux/arm64 -f Dockerfile.api .
docker compose build
```

Docker must be running before these commands can succeed.

## Local Compose validation

After building, start the stack:

```powershell
docker compose up -d
docker compose ps
docker compose logs --tail=100 api web caddy
Invoke-WebRequest http://localhost/health -UseBasicParsing
```

The public local entrypoint should be Caddy on port 80. The API and web containers are internal services.

## Oracle deployment target

Recommended Oracle configuration:

- Ubuntu ARM64 image.
- `VM.Standard.A1.Flex`.
- Allocate within the tenancy's Always Free quota.
- Public or reserved IP.
- Open inbound TCP ports 80 and 443.
- Restrict SSH to the administrator's IP when possible.
- Install Docker Engine and Docker Compose.
- Clone the GitHub repository.
- Create a production `.env` on the VM.
- Set `APP_DOMAIN` to the real domain name.
- Run `docker compose up -d --build`.

The Oracle VM will run:

```text
Caddy -> Next.js frontend
Caddy -> FastAPI/LangGraph API
API -> Supabase, Groq, GBFS, and optional BigQuery
```

## Production secrets

Configure these only on the Oracle VM, never in Git:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_DB_URL=
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
GOOGLE_APPLICATION_CREDENTIALS_JSON=
APP_DOMAIN=
```

The Mapbox public token belongs in the frontend production environment as `NEXT_PUBLIC_MAPBOX_TOKEN`. It is a public browser token, but it should still be restricted by allowed URLs in Mapbox.

## Still required before public launch

- Run and pass Docker ARM64 image builds.
- Run the complete Compose stack locally.
- Verify `/health`, frontend loading, API calls, and approval flow through Caddy.
- Add production API authentication or a protected demo token.
- Add rate limiting for `/api/tick`.
- Restrict production CORS instead of allowing every origin.
- Confirm Oracle firewall and OS firewall rules.
- Configure DNS and HTTPS through Caddy.
- Configure Git identity and review the final diff before pushing.
- Do not commit until the Docker and local Compose checks pass.

## Git authorship

Recent commits are authored by the project owner GitHub identity. No Claude, Anthropic, Codex, or `Co-authored-by` attribution markers were found in the inspected repository history. Configure your own Git identity before making new commits.

## Resume point

Resume at **Run local Docker/ARM64 validation**. Do not redo the persistence implementation or browser session work.
