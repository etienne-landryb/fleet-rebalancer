# Fleet Rebalancer Deployment Handoff

Last verified: 2026-09-08

The current authoritative deployment and maintenance record is [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md).

Current production endpoint:

```text
https://app.locafleet.de
```

Current infrastructure:

- Azure for Students subscription.
- Ubuntu 24.04 LTS x64 VM, `Standard_B2ats_v2`, Sweden Central.
- Resource group: `fleet-rebalancer-rg`.
- Docker Compose services: FastAPI/LangGraph API, Next.js web, and Caddy.
- Supabase PostgreSQL provides persistent LangGraph checkpoints and application metadata.

Before continuing, read `CLAUDE.md` and `OPERATIONS_RUNBOOK.md`. Never commit `.env`, `.env.local`, SSH keys, image archives, service-account JSON, or tokens.

The Firefox session-ID fix, large-network planner guard, and image-based country flags are deployed. See `REBOOT_CHECKPOINT.md` for the exact post-reboot resume sequence. Keep GitHub source and Azure images aligned after each runtime change.
