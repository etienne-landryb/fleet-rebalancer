# Fleet Rebalancer Deployment Handoff

Last verified: 2026-09-08

The current authoritative deployment and maintenance record is [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md).

Current production endpoint:

```text
http://20.240.135.196
```

Current infrastructure:

- Azure for Students subscription.
- Ubuntu 24.04 LTS x64 VM, `Standard_B2ats_v2`, Sweden Central.
- Resource group: `fleet-rebalancer-rg`.
- Docker Compose services: FastAPI/LangGraph API, Next.js web, and Caddy.
- Supabase PostgreSQL provides persistent LangGraph checkpoints and application metadata.

Before continuing, read `CLAUDE.md` and `OPERATIONS_RUNBOOK.md`. Never commit `.env`, `.env.local`, SSH keys, image archives, service-account JSON, or tokens.

The Firefox `crypto.randomUUID()` compatibility fix and the large-network planner guard are included in the current source changes. Keep GitHub source and the deployed Azure images aligned after this commit.
