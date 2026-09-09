# Reboot Checkpoint

Last verified: 2026-09-09

## Current state

The Fleet Rebalancer project is deployed and working publicly at:

```text
https://app.locafleet.de
```

Verified:

- HTTPS frontend returns HTTP 200.
- HTTPS `/api/status` returns HTTP 200.
- Caddy obtained a trusted Let's Encrypt certificate for `app.locafleet.de`.
- Azure VM is running Docker Compose services: API, web, and Caddy.
- API container is healthy.
- `docomo-cycle` large-network analysis reaches the approval stage without the previous 502 failure.
- Country flags are visible in the live system selector after the image-based flag fix.

## Current local repository state

At the last checkpoint, the local source had these pending changes:

```text
README.md
web/src/components/SystemSelector.tsx
```

The README documents the live deployment. The selector uses explicit `flagcdn.com` image assets instead of browser-dependent emoji rendering.

Do not commit or push until the visual flag fix and README have been reviewed. Preserve the owner-only Git identity:

```text
etienne-landryb
294482624+etienne-landryb@users.noreply.github.com
```

Never commit `.env`, `web/.env.local`, SSH keys, image archives, service-account JSON, or tokens. Do not add Claude, Anthropic, Codex, Copilot, or `Co-authored-by` metadata.

## After reboot: exact recovery sequence

Open Anaconda Prompt and run:

```cmd
cd /d "C:\Users\dell\Documents\00 TECH JOBS - GERMANY - 2026\05 AGENTIC LOGISTIC SYSTEM\TOOL"
conda activate rebalancer
git status --short --branch
git log -3 --format="%h %an <%ae> %s"
```

Then verify the public deployment from PowerShell or Anaconda Prompt:

```powershell
$app = Invoke-WebRequest -Uri "https://app.locafleet.de/" -UseBasicParsing -TimeoutSec 30
$api = Invoke-WebRequest -Uri "https://app.locafleet.de/api/status" -UseBasicParsing -TimeoutSec 30
$app.StatusCode
$api.StatusCode
```

Expected:

```text
200
200
```

Open the app in a browser and hard-refresh with `Ctrl+Shift+R`. Confirm that flags appear in the system selector.

## Resume actions

1. Review the visual flag fix and README.
2. Run the frontend build from `web/`:

```cmd
cd web
npm run build
```

3. From the repository root, run:

```cmd
cd ..
git diff --check
git add README.md web/src/components/SystemSelector.tsx
git -c user.name="etienne-landryb" -c user.email="294482624+etienne-landryb@users.noreply.github.com" commit -m "Document live deployment and improve system flags"
git push origin main
git status --short --branch
```

4. Do not rebuild Azure after a documentation-only change. The flag image is already deployed, but source and deployment must remain synchronized.
5. Continue next with public-demo hardening: reviewer access gate, `/api/tick` rate limiting, restricted CORS, and Azure cost alerts.

## Azure access

```cmd
ssh -o ServerAliveInterval=60 -o ServerAliveCountMax=10 -i "%USERPROFILE%\.ssh\fleet-rebalancer-vm_key.pem" azureuser@20.240.135.196
```

Inside Azure:

```bash
cd ~/fleet-rebalancer
docker compose ps
docker compose logs --tail=100 api web caddy
```

Do not rebuild on Azure. The VM is small and its student credit is nearly exhausted. Build locally and transfer only the changed Docker image when a runtime change is required.

## Important infrastructure facts

- Azure subscription: `Azure for Students`.
- Resource group: `fleet-rebalancer-rg`.
- VM: `fleet-rebalancer-vm`.
- Region: Sweden Central.
- Size: `Standard_B2ats_v2`, 2 vCPU, 4 GiB RAM.
- Public IP: `20.240.135.196`.
- Domain DNS: `app.locafleet.de` A record points to `20.240.135.196`.
- Supabase PostgreSQL stores plans, metadata, and LangGraph checkpoints.
- Caddy manages HTTPS and HTTP-to-HTTPS redirects.
