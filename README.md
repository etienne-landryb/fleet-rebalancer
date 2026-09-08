# Fleet Rebalancer

A LangGraph-based predictive-prescriptive system thar keeps shared-mobility networks balanced.
It forecasts which stations will run empty or full, plans van repositioning
routes to close the gap, and surfaces the plan to a human operator for approval
through a real-time operations console.

<img width="960" height="452" alt="image" src="https://github.com/user-attachments/assets/40a1782c-f3e8-48c6-a118-ebeb61896cb6" />
Built on live Citi Bike NYC data (~2,500 docked stations), with historical
training data from BigQuery's 30M+ trip archive. Supports any GBFS-compatible
system via the MobilityData catalog (~900 networks worldwide).

## How it works

A LangGraph state machine orchestrates the full decision loop every tick:

```
ingest ─► forecast ─► assess_imbalance
                          │
                    trigger=false ──► END (idle, 0 LLM calls)
                          │
                    trigger=true ──► plan ─► evaluate_plan
                                               │
                                      feasible ──► explain ─► human_approval
                                               │                  │
                                      infeasible ──► relax ──► plan (loop)
                                                          │
                                                   approved ──► dispatch ──► END
                                                   rejected ──► END
```

- **ingest** — polls GBFS `station_status` and `station_information` for live
  fill levels across all stations.
- **forecast** — XGBoost model predicts per-station demand at a configurable
  horizon (default 45 min). Trained on BigQuery historical trip data with
  temporal train/test split. Evaluated against persistence and seasonal-naive
  baselines. Falls back to persistence baseline for systems without a trained
  model.
- **assess_imbalance** — risk-scores each station by predicted fill level
  (starving ≤15%, saturated ≥85%). If the aggregate imbalance exceeds the
  threshold (default 30%), the tick triggers planning. Reports distinct idle
  reasons: healthy network, system-wide shortage, system-wide surplus, or
  below-threshold balance.
- **plan** — OR-Tools capacitated VRP maps surplus/deficit stations to van
  pickup/dropoff routes, respecting van capacity, fleet size, and shift budget.
  Operator-configurable constraints (van count, capacity, shift duration) flow
  from the UI into the solver.
- **evaluate_plan** — simulates network health improvement under a do-nothing
  counterfactual. If infeasible, the graph loops through `relax_constraints`
  (adds a van, extends shift budget) up to `MAX_REPLAN` times.
- **explain** — the single LLM call (Groq). Writes natural-language driver work
  orders from the plan. Falls back to a deterministic template if the LLM is
  unavailable. An idle tick makes zero LLM calls; a triggered tick makes
  exactly one.
- **human_approval** — the graph pauses via `interrupt()`. The operator console
  surfaces the plan with before/after KPIs. Approve dispatches the plan to
  Supabase; reject logs and ends.

All routing decisions use deterministic conditional edges (plain Python
predicates). The LLM never makes a control-flow decision.
<img width="959" height="448" alt="image" src="https://github.com/user-attachments/assets/3ef8687c-3b7a-434c-921c-fc564ef012b5" />

## Operator console

A Next.js application served alongside a FastAPI backend, designed as a
precision operations console — glassmorphism UI with dark/light/system themes,
monospaced data values, responsive layout.

| Panel | What it shows |
|-------|---------------|
| **KPI strip** | Network health %, starving/saturated station counts, data freshness |
| **Controls bar** | Van count (1–10), capacity (5–50), shift budget (60–240 min) steppers; scheduled auto-analysis (off/1h/2h/4h) |
| **Journey bar** | 7-step pipeline with animated node states (pending → running → done) |
| **Station health map** | Mapbox GL — stations colored by risk (starving/healthy/saturated), van routes overlaid with distinct per-van colors, interactive popups |
| **Plan panel** | Impact assessment (before/after health, starving, saturated), van route details, driver work orders, approve/reject buttons |
| **Decision trace** | Collapsible accordion showing which graph nodes fired, LLM call count, re-plan count |
| **At-risk stations** | Collapsible chart of top 15 stations by fill level with risk indicators |
| **History** | Collapsible table of last 10 approved plans from Supabase (timestamp, system, health delta, bikes moved, vans, status) |

The system selector supports any GBFS-compatible network. Citi Bike NYC is
pinned as the recommended default (ML model active). Other systems use a
persistence-baseline forecast.

## Architecture

```
src/rebalancer/
├── agents/          # LangGraph graph, state, nodes, edges
├── data/            # GBFS client, BigQuery client, Supabase client
├── ml/              # XGBoost forecaster, baselines, features, SHAP
├── optim/           # OR-Tools capacitated VRP planner
└── llm/             # Groq client with deterministic fallback

api/
├── tick.py          # Graph tick handler with constraint passthrough
├── approve.py       # Resume graph with approved decision
├── reject.py        # Resume graph with rejected decision
├── status.py        # Current graph state from checkpointer
└── _shared.py       # Response builder (KPIs, trace enrichment, idle reasons)

web/
├── src/app/page.tsx         # Layout orchestration, state management
├── src/components/          # 10 React components (Header, MapView, PlanPanel, etc.)
├── src/hooks/               # 5 custom hooks (useGbfs, useTick, useSystem, etc.)
└── src/lib/                 # API client, TypeScript types
```

Every major subsystem sits behind an interface (`Forecaster`, `Planner`,
`DataClient`, `LLMClient`) so any one can be swapped without touching the graph.

## Stack

| Layer | Tool |
|-------|------|
| Orchestration | LangGraph (StateGraph, interrupt, conditional edges, Postgres checkpointer) |
| ML | XGBoost (demand forecasting), SHAP (explainability) |
| Optimization | OR-Tools (capacitated VRP) |
| LLM | Groq free tier — one call per action tick, zero per idle tick |
| Live data | GBFS (Citi Bike NYC + any GBFS system via MobilityData catalog) |
| Historical data | BigQuery public datasets (citibike_trips, citibike_stations, NOAA weather) |
| Persistence | Supabase Postgres (station metadata + plans, kilobytes only) |
| Backend API | FastAPI with CORS middleware |
| Frontend | Next.js 15, React 19, Mapbox GL, Tailwind CSS |
| Maps | Mapbox GL JS (dark/light/navigation basemaps, Directions API for route geometry) |
| CI | GitHub Actions (lint + 58 tests on push, Supabase keepalive cron) |

100% free-tier / open-source. No paid APIs, no paid infra.

## Quick start

```bash
# 1. Create environment
conda env create -f environment.yml
conda activate rebalancer

# 2. Configure credentials
cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY
# BigQuery: set GOOGLE_APPLICATION_CREDENTIALS or run `gcloud auth application-default login`
# Mapbox: set NEXT_PUBLIC_MAPBOX_TOKEN in web/.env.local

# 3. Run tests
pytest

# 4. Train the forecaster (queries BigQuery — takes a few minutes)
python scripts/train_model.py

# 5. Start the API server
python scripts/local_server.py

# 6. Start the operator console (in a second terminal)
cd web
npm install
npm run dev
```

Open `http://localhost:3000`. Press **Run Analysis** to ingest live data, run
the full graph, and see the plan. Adjust van count, capacity, and shift budget
in the controls bar. Approve or reject from the plan panel.

## Data strategy

No heavy storage. Historical training data lives in BigQuery public datasets
(free, already there). Live station state is polled from GBFS into memory.
Supabase stores only station metadata and dispatched plans — well under 1 MB.

| Layer | Source | Cost |
|-------|--------|------|
| Historical (training) | BigQuery: `citibike_trips` (30M+ trips), `citibike_stations`, `noaa_gsod` | Free (1 TB/month sandbox) |
| Live (inference) | GBFS `station_status.json` polled every tick | Free, public JSON |
| Persistence | Supabase Postgres: `stations` + `plans` tables | Free tier |

## Honesty

This is a portfolio-grade reference implementation, not a production deployment.
All claimed metrics name their baseline and data window:

- Forecaster accuracy is reported against persistence and seasonal-naive
  baselines on a temporal train/test split from BigQuery trip data.
- Solver feasibility and network health improvement are measured against a
  stated do-nothing counterfactual.
- No claims are made about realized rider wait times, real-world trip savings,
  or superiority over commercial tools.

## License

MIT

## Author

Etienne Landry-Bessala
