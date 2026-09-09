# Fleet Rebalancer Operations Runbook

Last verified: 2026-09-08

## Current state

The application is live on an Azure for Students Linux VM and is reachable at:

```text
https://app.locafleet.de
```

Verified during deployment:

- Frontend returned HTTP 200 with title `Fleet Rebalancer`.
- `GET /api/status` returned HTTP 200.
- Docker API container was healthy.
- Docker Compose services API, web, and Caddy were running.
- The browser UUID compatibility fix was compiled locally and deployed in the web image.

The public deployment uses `app.locafleet.de`, whose DNS A record points to `20.240.135.196`. Caddy manages the trusted Let's Encrypt certificate and redirects HTTP to HTTPS.

## Infrastructure inventory

### GitHub

- Repository: `https://github.com/etienne-landryb/fleet-rebalancer.git`
- Branch: `main`
- Never commit `.env`, `.env.local`, SSH keys, image archives, service-account JSON, or tokens.
- Preserve project-owner Git authorship. Do not add AI attribution or `Co-authored-by` lines.

### Azure

- Subscription: `Azure for Students`.
- Resource group: `fleet-rebalancer-rg`.
- VM: `fleet-rebalancer-vm`.
- Region: `Sweden Central`.
- Image: Ubuntu Server 24.04 LTS x64 Gen2.
- Size: `Standard_B2ats_v2`, 2 vCPU, 4 GiB RAM.
- Public IP: `20.240.135.196`.
- Public hostname: `app.locafleet.de`.
- Private IP: `172.16.0.4`.
- SSH user: `azureuser`.
- Local key: `%USERPROFILE%\\.ssh\\fleet-rebalancer-vm_key.pem`.

The Azure portal showed approximately 95% of the student credit consumed. Treat the credit as a hard operational constraint: configure cost alerts, stop/deallocate the VM when it is not needed, and do not create additional Azure resources without checking cost first.

The VM has a public IP, Standard SSD OS disk, Basic NSG, no Azure Load Balancer, and inbound TCP ports 22, 80, and 443. Docker Engine, Buildx, and the Compose plugin were installed from Docker's official Ubuntu repository.

### Supabase

Supabase is the persistent external PostgreSQL service. It stores metadata, plans, and LangGraph checkpoint state. The API uses `PostgresSaver` when `SUPABASE_DB_URL` is configured and falls back to `MemorySaver` only when it is absent.

`PostgresSaver` is backed by a `psycopg_pool.ConnectionPool` (`api/_shared.py`), not a single raw connection. Supabase closes idle connections server-side; the pool health-checks and recycles connections automatically (`max_idle=120s`, `max_lifetime=1800s`), so this no longer requires restarting the `api` container. If `the connection is closed` ever reappears in `api` logs, it self-heals on the next request via the pool plus a one-time retry in `call_with_reconnect` — no manual intervention needed.

Previously verified LangGraph tables:

```text
checkpoints
checkpoint_blobs
checkpoint_writes
checkpoint_migrations
```

Do not store live station snapshots in Supabase.

### External services

- GBFS: live station data, primarily Citi Bike NYC.
- BigQuery: historical public Citi Bike training data.
- Groq: one explanation call on action ticks; deterministic fallback when unavailable.
- Mapbox: browser map token in `web/.env.local`; restrict allowed URLs.

## Runtime topology

```text
Internet :80/:443
        |
      Caddy
       |---- /api/* -> api:8000 (FastAPI/LangGraph)
       |---- /*     -> web:3000 (Next.js standalone)

api -> Supabase PostgreSQL, Groq, GBFS, BigQuery as configured
```

The API and web ports are internal Docker ports. Do not expose 8000 or 3000 through Azure or host port mappings.

## Important files

- `Dockerfile.api`: Python 3.11 API image; includes `src`, `api`, and tracked `models`.
- `Dockerfile.web`: Node 22 Alpine multi-stage Next.js standalone image.
- `docker-compose.yml`: API, web, and Caddy with restart policies and API healthcheck.
- `Caddyfile`: routes `/api/*` to FastAPI and all other paths to Next.js.
- `.dockerignore`: excludes secrets, caches, local dependencies, and build output.
- `.env.example`: safe variable template; real values belong only in local or VM environments.

## Connect and inspect

Run from Windows Command Prompt or PowerShell:

```powershell
ssh -i "$env:USERPROFILE\\.ssh\\fleet-rebalancer-vm_key.pem" azureuser@20.240.135.196
```

Inside the VM:

```bash
cd ~/fleet-rebalancer
docker compose ps
docker compose logs --tail=100 api web caddy
curl -fsS http://127.0.0.1/api/status
```

Restart without rebuilding:

```bash
docker compose up -d --no-build
```

Stop without deleting Caddy volumes:

```bash
docker compose down
```

Do not use `docker compose down -v` unless intentionally deleting Caddy certificate/config volumes.

## Deployment procedure

### Source deployment

1. Run tests locally.
2. Build the web image locally from `web/` and review the source diff.
3. Commit and push the intended source to GitHub.
4. On Azure, pull with `git pull --ff-only origin main`.
5. Update the VM-only `.env` and `web/.env.local` without printing them.
6. Use `docker compose up -d --no-build` when images are already present.

The Azure VM is small and the first remote build spent hours downloading Python and Node dependencies before the SSH connection reset. Prefer local builds and image transfer for this VM.

### Transfer only the updated web image

Windows, from the repository root:

```powershell
docker compose build web
docker tag tool-web:latest fleet-rebalancer-web:latest
docker save -o "$env:USERPROFILE\\fleet-rebalancer-web-fix.tar" fleet-rebalancer-web:latest
scp -i "$env:USERPROFILE\\.ssh\\fleet-rebalancer-vm_key.pem" "$env:USERPROFILE\\fleet-rebalancer-web-fix.tar" azureuser@20.240.135.196:/home/azureuser/fleet-rebalancer-web-fix.tar
```

Azure:

```bash
docker load -i ~/fleet-rebalancer-web-fix.tar
cd ~/fleet-rebalancer
docker compose up -d --no-build web
docker compose ps
```

For a full image transfer, use `docker save` locally and `docker load` on Azure. Do not rebuild the API remotely unless necessary.

### Public checks

From Windows:

```powershell
$root = Invoke-WebRequest http://20.240.135.196/ -UseBasicParsing
$status = Invoke-WebRequest http://20.240.135.196/api/status -UseBasicParsing
$root.StatusCode
$status.StatusCode
```

In Firefox, hard-refresh with `Ctrl+Shift+R`, then load a system, click Run Analysis, inspect the trace, and test approval/rejection only when a plan is produced.

## Environment and secrets

Never put secret values in this document. The VM `.env` uses names represented by:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_DB_URL=
GROQ_API_KEY=
GROQ_MODEL=
GBFS_PRIMARY_DISCOVERY_URL=
GBFS_PRIMARY_SYSTEM_ID=
GOOGLE_APPLICATION_CREDENTIALS=
FORECAST_HORIZON_MIN=
IMBALANCE_THRESHOLD=
MAX_REPLAN=
VAN_COUNT=
VAN_CAPACITY=
SHIFT_BUDGET_MIN=
PG_WINDOW_HOURS=
APP_DOMAIN=
```

The frontend file contains `NEXT_PUBLIC_MAPBOX_TOKEN` and must remain outside Git. The VM uses `APP_DOMAIN=app.locafleet.de`.

The VM received image archives of approximately 920 MB and 71 MB. Delete them only after confirming the deployment and keeping any required rollback copy.

## Cost protection and maintenance

1. Create an Azure Cost Management budget/alert immediately.
2. Stop/deallocate the VM when it is not needed.
3. Do not create extra VMs, disks, load balancers, gateways, managed databases, or monitoring workspaces without checking credit impact.
4. Keep Supabase as the database.
5. Inspect disk usage periodically:

```bash
docker system df
docker image ls
df -h
```

Use `docker image prune` only after confirming no rollback image is needed. Avoid broad `docker system prune -a` during an incident.

## Security work still required

- Add API authentication or a protected demo token.
- Restrict CORS from `*` to the actual frontend origin.
- Restrict SSH NSG source to the administrator's current IP.
- Add rate limiting for `/api/tick`.
- Rotate any credential exposed outside the VM.
- Add Supabase metadata/plan backup or export instructions.
- Add a documented shutdown schedule.

## Current source divergence

`web/src/lib/api.ts` contains the fix for Firefox on the plain HTTP IP origin. It uses `crypto.randomUUID()` when available, `crypto.getRandomValues()` as the fallback, and a last-resort timestamp/random identifier. The fix was compiled and deployed in the web image. `src/rebalancer/optim/planner.py` also bounds large-network routing at 500 active stations and reports skipped lower-priority stations as unserved.

## Next-session checklist

1. Read `CLAUDE.md`, `DEPLOYMENT_HANDOFF.md`, `REBOOT_CHECKPOINT.md`, and this file.
2. Run `git status --short --branch`.
3. Run the focused frontend build from `web/`.
4. Commit and push the reviewed browser and planner fixes without secrets or archives.
5. Check Azure credit and create cost alerts before more deployment work.
6. Check `docker compose ps` and the public HTTP status.
7. Do not rebuild on Azure unless resource and credit headroom are confirmed.
