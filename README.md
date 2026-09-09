# Fleet Rebalancer

Fleet Rebalancer is a predictive-prescriptive operations console for shared-mobility networks. It reads live GBFS station feeds, forecasts near-term station demand, identifies stations likely to become empty or full, plans capacitated van repositioning routes, estimates the result against a do-nothing baseline, and pauses for human approval before dispatch.

## Live Demo

**Reviewer URL:** [https://app.locafleet.de](https://app.locafleet.de)

The live demo is deployed on an Azure for Students Ubuntu VM. It runs the Next.js console, FastAPI/LangGraph backend, and Caddy reverse proxy in Docker Compose. HTTPS is provided by Caddy with an automatically managed Let's Encrypt certificate.

The demo is an interactive portfolio system, not a production fleet-control service. Its projected impact is a simulation based on live station state and stated solver assumptions. It does not claim to measure realized rider wait times, real-world trip savings, or superiority over commercial tools.

## What It Demonstrates

- Live GBFS ingestion for Citi Bike NYC and other catalogued systems.
- A deterministic LangGraph decision loop with conditional branching and a human approval gate.
- XGBoost demand forecasting for Citi Bike NYC, with persistence-baseline forecasting for other systems.
- OR-Tools capacitated vehicle-routing plans with configurable van count, capacity, and shift budget.
- A single Groq explanation call for an action tick, with a deterministic fallback when Groq is unavailable.
- Persistent LangGraph checkpoints and dispatched plan metadata in Supabase PostgreSQL.
- A browser-based operator console with station risk map, KPIs, route overlays, projected impact, work orders, trace, and plan history.

## Decision Loop

```text
ingest -> forecast -> assess_imbalance
                           |
                 trigger=false -> END
                           |
                 trigger=true -> plan -> evaluate_plan
                                      |              |
                         feasible/improving     infeasible
                                      |              |
                                  explain       relax_constraints
                                      |              |
                              human_approval <- plan
                                |       |
                         approved       rejected
                                |       |
                            dispatch    END
```

The control flow is deterministic Python. The LLM does not choose branches, approve plans, or control the optimizer.

### Graph nodes

- **ingest**: fetches `station_information` and `station_status` from the selected GBFS discovery URL.
- **forecast**: predicts station-level bikes at the configured horizon. The checked-in XGBoost model is used for Citi Bike NYC; other systems use persistence.
- **assess_imbalance**: classifies stations as starving at 15% fill or below and saturated at 85% fill or above.
- **plan**: solves a capacitated repositioning problem with OR-Tools.
- **evaluate_plan**: compares the proposed result with a do-nothing simulation.
- **relax_constraints**: increases van count and shift budget within the configured re-plan limit.
- **explain**: writes the operator-facing work order. This is the only LLM node.
- **human_approval**: pauses the graph through LangGraph `interrupt()`.
- **dispatch**: persists an approved plan to Supabase.

For very large systems, the planner bounds the active routing set at 500 high-priority surplus/deficit stations to avoid quadratic distance-matrix growth on small compute instances. Lower-priority stations are reported as unserved rather than silently treated as planned.

## Operator Console

The Next.js console provides:

| Panel | Function |
| --- | --- |
| KPI strip | Network health, starving/saturated counts, and data freshness |
| Controls | Van count, van capacity, shift budget, and scheduled analysis |
| Journey bar | Monitor, detect risk, forecast, plan, compare, approve, dispatch |
| Station map | Mapbox station health, filters, popups, and van routes |
| Plan panel | Before/after impact, route stops, work order, approve/reject |
| Decision trace | Fired nodes, branch history, LLM calls, and re-plan count |
| At-risk stations | Highest-risk stations and fill-level visualization |
| History | Previously approved plans loaded from Supabase |

The system selector uses the MobilityData GBFS catalog. Citi Bike NYC is the recommended demonstration system because the repository includes a trained model for it. Systems without a trained model use the persistence baseline. Very large networks may complete with unserved stations because the route planner applies an active-node limit.

## Architecture

```text
Browser
  |
  | HTTPS https://app.locafleet.de
  v
Caddy :80/:443
  |-- /api/* -> FastAPI :8000
  `-- /*     -> Next.js :3000

FastAPI/LangGraph
  |-- GBFS live feeds
  |-- Supabase PostgreSQL
  |-- Groq explanation call
  `-- optional BigQuery access for training workflows
```

The API and web ports are internal Docker ports. Caddy is the only public application entry point.

## Repository Layout

```text
src/rebalancer/
├── agents/          # LangGraph state, graph, nodes, and edges
├── data/            # GBFS, BigQuery, Supabase, and weather clients
├── ml/              # features, baselines, XGBoost forecaster, SHAP
├── optim/           # OR-Tools planner and impact simulation
└── llm/             # Groq client and deterministic fallback

api/                 # FastAPI deployment bridge
web/                 # Next.js operator console
scripts/             # training, GBFS, BigQuery, and local-server scripts
tests/               # unit and integration-oriented tests
models/              # checked-in inference artifact and generated metrics
```

Operational deployment and maintenance details are documented in [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md). The short deployment checkpoint is in [DEPLOYMENT_HANDOFF.md](DEPLOYMENT_HANDOFF.md).

## Technology Stack

| Layer | Technology |
| --- | --- |
| Orchestration | LangGraph with StateGraph, conditional edges, interrupt, and Postgres checkpointer |
| Backend | FastAPI, Uvicorn, Python 3.11 |
| Forecasting | XGBoost, scikit-learn baselines, SHAP |
| Optimization | OR-Tools capacitated vehicle routing |
| Explanation | Groq, one call per action tick at most |
| Live data | GBFS station information and station status feeds |
| Historical data | BigQuery public Citi Bike and NOAA datasets |
| Persistence | Supabase PostgreSQL for metadata, plans, and checkpoints |
| Frontend | Next.js 16, React 19, TypeScript |
| Maps | Mapbox GL and Directions API for route geometry |
| Proxy/TLS | Caddy 2 with automatic HTTPS |
| Packaging | Docker Compose |
| CI | GitHub Actions with Ruff, isort, Black, and pytest |

## Local Development

### Requirements

- Windows with Anaconda Prompt, or a compatible Python environment.
- Python 3.11 environment from `environment.yml`.
- Node.js 22 for the web console.
- Docker Desktop if running the complete Compose stack.

### Python setup

From Anaconda Prompt:

```cmd
conda env create -f environment.yml
conda activate rebalancer
```

Copy `.env.example` to `.env` and fill only the credentials needed for the selected workflow. Never commit `.env`.

The frontend map token belongs in `web/.env.local`:

```env
NEXT_PUBLIC_MAPBOX_TOKEN=your_public_mapbox_token
```

This token is browser-visible and should be restricted by allowed URLs in Mapbox.

### Tests and lint

```cmd
pytest -q
ruff check src/ tests/
isort --check-only src/ tests/
black --check src/ tests/
```

### Run the development services

Start the API from the repository root:

```cmd
python scripts/local_server.py
```

In a second Anaconda Prompt:

```cmd
cd web
npm install
npm run dev
```

Open `http://localhost:3000`.

### Local Docker Compose

```cmd
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

The local Compose entry point is Caddy on port 80. API and web containers are internal.

## Data and Persistence

The project deliberately avoids a heavy snapshot warehouse:

| Layer | Source | Purpose |
| --- | --- | --- |
| Historical training | BigQuery public datasets | Trip aggregates, station metadata, optional weather |
| Live inference | GBFS JSON feeds | Current station fill and availability |
| Persistent application state | Supabase PostgreSQL | Station metadata, plans, and LangGraph checkpoints |

The persistence baseline is the reporting bar for forecasting. Forecast metrics should identify the temporal train/test window and compare the model against persistence and seasonal-naive baselines. Solver results are simulations against a stated do-nothing counterfactual.

## Deployment

The current live deployment is:

- Azure for Students subscription.
- `fleet-rebalancer-vm` in the Sweden Central region.
- Ubuntu 24.04 LTS x64, `Standard_B2ats_v2`, 2 vCPU and 4 GiB RAM.
- Docker Compose services: API, web, and Caddy.
- Supabase PostgreSQL for durable state.
- Public URL: `https://app.locafleet.de`.

The Azure student credit was close to exhausted during deployment. The VM is a demo host, not an unlimited free production platform. Configure cost alerts and deallocate the VM when it is not needed.

Because the Azure VM is small, build images locally and transfer them when a dependency-heavy image changes. Avoid rebuilding the API remotely unless there is sufficient resource and credit headroom. Follow [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) for the exact SSH, image transfer, restart, cleanup, and verification commands.

## Security and Public Demo Scope

HTTPS protects traffic between reviewers and the application. Before unrestricted public promotion, the deployment should also add:

- API authentication or a protected reviewer/demo token.
- Rate limiting for `/api/tick`.
- CORS restricted to `https://app.locafleet.de`.
- SSH access restricted to the administrator's current IP.
- A documented shutdown and cost-alert procedure.
- Backup/export guidance for Supabase plans and metadata.

Until those controls are in place, treat the live URL as a controlled reviewer demo. Do not submit real operational data, credentials, or sensitive rider information.

## Honest Scope

This is a portfolio-grade reference implementation of the fleet-repositioning pattern.

- Forecast accuracy is evaluated against explicit baselines on temporal data splits.
- Route feasibility and projected health changes are simulated, not measured in production operations.
- A large network may return a valid approval state with unserved stations because of the planner's bounded active set.
- The system does not claim realized wait-time reduction, guaranteed rider savings, or superiority over commercial fleet-management tools.

## License

MIT

## Author

Etienne Landry-Bessala
