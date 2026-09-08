# CLAUDE.md — Fleet Rebalancer

Read this file at the start of every session. It contains everything you need.
No other doc is needed to start building. Work through the build plan one phase
at a time, stopping at each checkpoint for the owner (Etienne) to review.

---

## 1. What this is

A **predictive-prescriptive system** for keeping shared-mobility networks
(bikes/scooters) balanced. It forecasts which stations will run empty or full,
plans van repositioning routes to close the gap, and surfaces the plan to a
human operator for approval.

- **LangGraph** orchestrates the decision loop (not a linear pipeline).
- **XGBoost/LightGBM** forecasts station-level demand.
- **OR-Tools** solves the capacitated vehicle routing problem.
- **Groq LLM** writes the driver work order — the **only** LLM call in the
  system.
- The UI is an **operator console** (Streamlit) where the decision and its
  value are visible at a glance.

It is a portfolio-grade reference implementation of the **fleet-repositioning
pattern** — a problem that SIXT (car-sharing), Nextbike, DHL (locker
servicing), ambulance deployment, ATM replenishment, and many others solve
commercially. The demo runs on live feeds of companies that face this problem
every day.

---

## 2. Hard constraints (non-negotiable)

1. **100% free-tier / open-source.** No paid APIs, no paid infra. If a task
   seems to need a paid service, STOP and ask. This is the condition under
   which a solo engineer builds a real portfolio.
2. **Deterministic-first.** All routing and decision logic is plain code. ML is
   classical/tabular. The LLM is used at exactly one node (explanation) and
   nowhere else.
3. **Minimize LLM calls.** An idle tick = 0 LLM calls. An action tick = exactly
   1. Never add an LLM call to a control-flow decision.
4. **No heavy data storage.** Historical training data lives in BigQuery public
   datasets (free, already there). Live state is in-memory. Supabase stores
   only metadata, plans, and checkpointer state (kilobytes, not megabytes).
5. **Secrets never touch the repo.** All credentials come from `.env` or
   platform secret stores.

---

## 3. The build discipline

- Work through the build plan (§12) **one phase at a time, in order.**
- **Do NOT start a new phase until Etienne has reviewed and approved.** At each
  checkpoint: summarize what you built, give the exact commands to run/verify,
  list what the owner should check, then **STOP and wait.**
- Commit in small, reviewable units. One logical change per commit.
- Write tests as you build the thing they test, not "later."
- Prefer editing existing files over creating parallel ones.

### Ask before you do these
- Installing a dependency not in the stack list (name it and say why).
- Changing any settled decision (§11).
- Any destructive git operation (force-push, history rewrite, branch delete).
- Deploying anything or creating/altering cloud resources.
- Writing to Supabase with anything other than the app's own tables.

---

## 4. Environment

- **OS:** Windows 10. Git runs from the **Anaconda Prompt.** Assume Windows
  paths and shell; never emit bash-only commands without a Windows equivalent.
- **Python:** 3.11 in a conda env named `rebalancer` (from `environment.yml`).
  Activate with `conda activate rebalancer`.
- **Backend:** Supabase (Frankfurt / eu-central) — metadata + plans +
  checkpointer only.
- **Deploy:** Streamlit Community Cloud (secrets in the platform).
- **Scheduler:** GitHub Actions cron (free).
- **LLM:** Groq free tier.

---

## 5. Data strategy (the key design — read carefully)

### Why no heavy storage

Citi Bike at 5-min polls = ~602K rows/day. The Supabase free Postgres is 500 MB
— full in ~1–2 weeks. Rather than build a Parquet archive + object store + DuckDB
warehouse + retention job, we eliminate the problem: **the historical data
already exists at scale, free, in BigQuery.**

### Three data layers

| Layer | What | Where | Cost |
|-------|------|-------|------|
| **Historical (training)** | 30M+ Citi Bike trips since 2013, station metadata, NOAA weather | BigQuery public datasets — query in place | Free (1 TB queries/month, no credit card via sandbox) |
| **Live (inference)** | Current station fill levels, updated every ~30s | GBFS `station_status.json` — polled into memory | Free, public JSON, no key |
| **Persistence (tiny)** | Station metadata cache, plans, LangGraph checkpointer | Supabase Postgres | Free tier, well under 1 MB |

### BigQuery public datasets we use

```
bigquery-public-data.new_york_citibike.citibike_trips
  → start_station_id/name, end_station_id/name, starttime, stoptime, tripduration, bikeid
  → derive: net flow per station per time window (departure = −1, arrival = +1)
  → this IS the training data — years of it, no collection wait

bigquery-public-data.new_york_citibike.citibike_stations
  → station_id, name, lat, lon, capacity, num_bikes_available
  → metadata + a live-ish snapshot (but GBFS is fresher for inference)

bigquery-public-data.noaa_gsod
  → daily weather observations, joinable by date + station
  → optional enrichment feature for the forecaster
```

### GBFS live feed (inference time)

Primary target: **Citi Bike NYC** (~2,090 docked stations).
- Discovery: `https://gbfs.citibikenyc.com/gbfs/gbfs.json`
- `station_information.json` — static: id, name, lat/lon, capacity
- `station_status.json` — live: `num_bikes_available`, `num_docks_available`,
  `is_renting`, `is_returning`, `last_reported`

Ingestion is catalog-driven (MobilityData's `systems.csv`) so adding systems is
a config change. But rebalancing is intra-city, so density (one big network)
matters more than breadth (many small ones).

### Feature engineering (training → model)

From BigQuery trip data, aggregate per station per time window:
- **Demand features:** pickups, dropoffs, net flow (hourly or sub-hourly)
- **Calendar:** hour-of-day, day-of-week, is-weekend, is-holiday
- **Station attributes:** capacity, geographic cluster
- **Weather (optional):** temperature, precipitation from NOAA, joined by date

At inference time: current GBFS fill + predicted demand at horizon H →
predicted fill → imbalance assessment.

### Why this won't force a mid-build switch

- Citi Bike trips have been in BigQuery since 2013, stable, updated regularly.
- GBFS has been stable for years (people archive it every 5 min).
- BigQuery sandbox is structural to Google Cloud's go-to-market — it's how they
  onboard users.
- The query layer sits behind an interface: the model receives a DataFrame, not
  a BigQuery client. If the source ever moved, the model wouldn't change.
- Auxiliary sources (weather, holiday calendar) are backfillable/static — planned
  additions, not mid-way discoveries.

---

## 6. Architecture — the LangGraph graph

### Principle

Deterministic tools do the work, the graph does the deciding, the LLM only
writes the explanation. Most ticks end in "no action" without touching the LLM.

### Shared state

```python
from typing import TypedDict, Literal
from datetime import datetime

class RebalanceState(TypedDict):
    tick_time: datetime
    system_id: str            # which GBFS system
    stations: dict            # live snapshot: bikes, docks, capacity per station
    weather: dict             # optional feature
    forecast: dict            # predicted demand / fill per station at horizon H
    imbalance: dict           # risk score per station + aggregate metric
    trigger: bool             # imbalance crossed the action threshold?
    fleet: dict               # vans: positions, capacity, shift budget left
    constraints: dict         # relaxable: van count, horizon, min-priority
    plan: list                # OR-Tools routes: pickup/dropoff per van
    plan_feasible: bool
    replan_count: int         # loop guard (max from settings)
    projected_impact: dict    # do-nothing vs plan KPIs
    approval: Literal["pending", "approved", "rejected"]
    work_orders: str          # LLM output: driver instructions + rationale
    decision_trace: list      # per-node log — feeds the UI panel
```

### Nodes

| Node | Layer | What it does |
|------|-------|-------------|
| `ingest` | deterministic | Poll GBFS station_status + station_information; assemble snapshot |
| `forecast` | ML (XGBoost) | Predict demand/fill per station at horizon H |
| `assess_imbalance` | deterministic | Risk-score stations; compute aggregate; set `trigger` |
| `plan` | deterministic | OR-Tools capacitated VRP → repositioning routes |
| `evaluate_plan` | deterministic | Simulate impact; check feasibility vs shift budget |
| `relax_constraints` | deterministic | Loosen a limit (add van / extend horizon); increment `replan_count` |
| `explain` | **LLM (Groq)** | Write driver work orders + "why this plan" — **the only LLM call** |
| `human_approval` | HITL | `interrupt()` — graph pauses, plan surfaces in UI, resumes on decision |
| `dispatch` | deterministic | Persist approved plan + work orders to Supabase |

### Edges (conditional, deterministic — never LLM-routed)

```
ingest → forecast → assess_imbalance
  ├─ trigger = False → END (idle tick, 0 LLM calls)
  └─ trigger = True → plan → evaluate_plan
                         ├─ feasible & improving → explain → human_approval
                         │                                    ├─ approved → dispatch → END
                         │                                    └─ rejected → END (log)
                         ├─ not feasible & replan_count < MAX → relax_constraints → plan (loop)
                         └─ not feasible & replan_count ≥ MAX → explain (best-effort, flagged)
```

### Multi-agent honesty

This is one stateful graph with specialized nodes — correctly called "agentic
orchestration" (event-driven triggering, re-plan loop, human gate, conditional
branching), not strictly "multi-agent" in the negotiating-agents sense. Describe
it precisely. A supervisor + specialist subgraphs is a possible v2.

---

## 7. Module layout

```
fleet-rebalancer/
├── CLAUDE.md                         # THIS FILE — the operating manual
├── README.md                         # public-facing, honest, written last (Phase 6)
├── environment.yml                   # conda env definition
├── pyproject.toml                    # black, isort, ruff, pytest config
├── .env.example                      # credential template (never commit .env)
├── .gitignore
│
├── src/rebalancer/
│   ├── __init__.py
│   ├── config.py                     # typed settings from .env (pydantic-settings)
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── gbfs_client.py            # discover + fetch + validate GBFS feeds
│   │   ├── bigquery_client.py        # query trip/station/weather data (behind interface)
│   │   ├── supabase_client.py        # tiny persistence: stations, plans, checkpointer
│   │   └── weather.py                # optional: Open-Meteo for live forecast enrichment
│   │
│   ├── ml/
│   │   ├── __init__.py
│   │   ├── features.py               # derive demand features from BQ trip aggregates
│   │   ├── baselines.py              # persistence + seasonal-naive (the bar to beat)
│   │   ├── forecaster.py             # train/predict behind a Forecaster interface
│   │   └── explain_shap.py           # SHAP feature importance
│   │
│   ├── optim/
│   │   ├── __init__.py
│   │   └── planner.py                # OR-Tools VRP behind a Planner interface
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── state.py                  # RebalanceState TypedDict
│   │   ├── graph.py                  # build the LangGraph graph
│   │   ├── nodes.py                  # node functions (wrapping data/ml/optim/llm)
│   │   └── edges.py                  # conditional-edge predicates (pure Python)
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   └── groq_client.py            # single explanation call + deterministic fallback
│   │
│   └── ui/
│       ├── __init__.py
│       ├── app.py                    # Streamlit operator console
│       └── components/
│           ├── __init__.py
│           ├── map_view.py           # pydeck: now-vs-predicted station health + route overlay
│           ├── plan_panel.py         # recommended plan + before/after delta + approve/reject
│           ├── work_order.py         # LLM-generated driver instructions
│           ├── trace.py              # decision trace strip (which nodes fired, branches taken)
│           ├── heatmap.py            # station × hour risk heatmap (plotly)
│           └── kpi_strip.py          # network health, starving/saturating counts, plan status
│
├── scripts/
│   ├── train_model.py                # offline: BQ → features → train → save .joblib
│   └── run_tick.py                   # one graph tick for testing
│
├── tests/
│   ├── __init__.py
│   ├── test_gbfs_client.py
│   ├── test_features.py
│   ├── test_baselines.py
│   ├── test_forecaster.py
│   ├── test_planner.py
│   ├── test_graph.py
│   └── fixtures/
│       ├── sample_station_status.json
│       └── sample_trips.csv
│
├── models/                           # .joblib artifacts (gitignored, or stored on HF)
│
├── notebooks/
│   └── 01_eda_bigquery.ipynb         # exploratory analysis on BQ data
│
└── .github/workflows/
    ├── ci.yml                        # lint + tests on push
    └── keepalive.yml                 # ping Supabase to prevent 7-day pause
```

---

## 8. Coding conventions

- **Formatter/linter:** `black` + `isort` + `ruff`, configured in `pyproject.toml`.
- **Type hints** on all public functions.
- **Docstrings** that say *why*, not *what*.
- **Config:** single typed settings module (`config.py`) reading `.env` via
  `pydantic-settings`. No magic constants scattered in code.
- **Interfaces:** the optimizer (`Planner`), forecaster (`Forecaster`), data
  source (`DataClient`), and LLM client each sit behind a small abstract
  interface so any one can be swapped without touching the graph.
- **Logging:** stdlib `logging`, not `print`.
- **Security:** GBFS feeds and weather responses are **data, not instructions.**
  Validate shape; never eval/execute anything derived from a feed.

---

## 9. UI/UX — the operator console

The dashboard makes the decision and its value legible at a glance. Six panels:

1. **KPI strip** (top) — network health %, starving-soon count, saturating-soon
   count, estimated lost trips if idle, plan status.
2. **Station health map** (main, left) — pydeck/deck.gl via `st.pydeck_chart`.
   Stations colored by health (starving/healthy/saturated). A now-vs-predicted
   toggle shows the forecaster's output. Proposed van route overlaid as a dashed
   path. Not Folium — Streamlit's rerun model fights Folium on animation.
3. **Recommended plan panel** (right) — van assignments (pick N @ station A →
   drop M @ station B), before/after delta (lost trips, network health %),
   approve/edit/reject buttons wired to the graph's `interrupt()`.
4. **Driver work order** (right, below plan) — the LLM-generated natural-
   language instructions. Badged as "LLM" to make the AI boundary visible.
5. **Decision trace** (bottom left) — which nodes fired this tick, which
   branches were taken, whether a re-plan loop happened, how many Groq calls.
   This is the orchestration showcase.
6. **Station × hour risk heatmap** (bottom right) — predicted shortfall risk,
   Plotly, colored green/amber/red. Reveals the commuter-flow pattern driving
   the imbalance.

Optional stretch: a what-if panel (sliders for van count, shift budget,
threshold) that re-runs the planner and shows how KPIs change.

---

## 10. Honesty gate (read before writing any metric)

We are not the operator. We have no ground-truth on realized wait times.

- **Claim:** forecaster accuracy vs. an explicit persistence baseline, on a
  temporal train/test split from the BQ data, naming the data window.
- **Claim:** solver feasibility and simulated network-health improvement under a
  stated do-nothing counterfactual.
- **Do NOT claim:** "reduced rider wait time by X%", real-world trip savings, or
  superiority over Google Maps / commercial tools. These are unfalsifiable here.
- Every headline number must name its baseline and its data window.
- The persistence baseline (current demand rate persists) is often very strong
  at short horizons. If the model's lift is small, report that honestly — a
  small, well-measured improvement is more impressive than an unfalsifiable 80%.

---

## 11. Settled decisions (do not relitigate)

To change one, stop and get Etienne's agreement first.

1. **GBFS, not GTFS-RT.** Free, open, uniform JSON, real-time, 1000+ systems.
   The rebalancing problem has a genuine agentic control loop; transit delay
   prediction is a linear pipeline. The free GTFS-RT feed also lacked vehicle
   positions.

2. **Citi Bike NYC as the primary target.** ~2,090 docked stations, stable
   feed, 30M+ trips in BigQuery. Density + reliability for the best model and
   routing showcase. Ingestion is catalog-driven (MobilityData `systems.csv`)
   so adding systems is a config change.

3. **BigQuery for historical data, not self-collected snapshots.** Eliminates
   all heavy storage, the Parquet/R2/DuckDB layer, and the 2–4 week data-
   collection wait. The "big data" skill is demonstrated at the query layer.

4. **OR-Tools, not Gurobi.** Free/open constraint. Behind a `Planner` interface
   so Gurobi could be swapped later.

5. **Deterministic conditional edges.** Routing decisions are plain Python
   predicates, not LLM calls. This is the honest reading of "minimize API
   calls."

6. **Single stateful graph, described precisely.** Called "agentic orchestration",
   not "multi-agent." Supervisor + subgraphs is a possible v2.

7. **Persistence baseline is the bar.** The forecaster is reported against
   persistence + seasonal-naive on a temporal split.

8. **pydeck for maps, not Folium.** Streamlit's rerun model fights Folium.
   Plotly for heatmap/KPI/trace.

9. **One LLM node with a deterministic fallback.** If Groq is unavailable, emit
   a templated work order. The graph never hard-fails on the LLM.

10. **No heavy storage.** Supabase holds KB (metadata, plans, checkpointer).
    BigQuery holds the history (already there). GBFS is in-memory. No Parquet,
    no R2, no archive, no retention job.

---

## 12. Build plan (checkpoint-gated)

Work these phases **in order.** Each ends with **STOP** — do not begin the next
until Etienne reviews and says go.

---

### Phase 0 — Scaffold

**Goal:** clean, runnable skeleton with tooling, config, CI — no features.

**Tasks:**
- Create the full tree from §7. `pyproject.toml` with black, isort, ruff,
  pytest. `environment.yml` with pinned versions (check current stable versions
  before pinning).
- `config.py`: typed settings loading `.env` via pydantic-settings.
- `.env.example` with all credential placeholders (see §13).
- `.gitignore` excluding `.env`, `data/`, `models/`, caches, IDE files.
- `ci.yml`: lint + tests on push. One trivial passing test.
- `README.md` stub: one paragraph + "see CLAUDE.md" + quick start.
- MIT `LICENSE` file.

**Done when:** `conda env create -f environment.yml`, `conda activate rebalancer`,
`pytest`, and linters all pass locally; CI is green on first push.

**Verify:** create env, run `pytest` → green. Inspect the tree.

> **STOP — wait for review.**

---

### Phase 1 — GBFS client + BigQuery client

**Goal:** prove the two data paths work end-to-end before building anything on
top.

**Tasks:**
- `gbfs_client.py`: discover endpoints from a GBFS discovery URL, fetch and
  validate `station_information` + `station_status`. Handle missing feeds and
  malformed rows. Confirm Citi Bike NYC has live, changing, docked data.
- `bigquery_client.py`: query `citibike_trips` and `citibike_stations` via the
  BigQuery sandbox (use `google-cloud-bigquery` with no credentials needed for
  public datasets, or use the REST API). Behind a `DataClient` interface so
  the model receives a DataFrame regardless of source.
- `supabase_client.py`: connect, upsert station metadata. Confirm the tiny
  persistence layer works.
- `keepalive.yml`: GitHub Actions cron pinging Supabase every 3 days to prevent
  the 7-day inactivity pause.
- Tests with fixture JSON for GBFS parsing; a small BQ query integration test.

**Done when:** a script fetches live GBFS data for Citi Bike, another script
queries BQ trip counts by station, and Supabase has station metadata rows.

**Verify:** run each script; see real data printed; check Supabase rows.

> **STOP — wait for review.**

---

### Phase 2 — Forecaster + baseline (the honesty gate)

**Goal:** predict per-station demand at horizon H, and prove it beats naive
baselines — or report honestly that it barely does.

**Tasks:**
- `features.py`: from BQ trip aggregates, derive hourly demand features per
  station (pickups, dropoffs, net flow) + calendar features (hour, day-of-week,
  weekend, holiday). Weather optional (Open-Meteo / NOAA), added only after the
  base model works.
- `baselines.py`: **persistence** (current demand rate persists) and
  **seasonal-naive** (same slot last week). These are the bar to beat.
- `forecaster.py`: XGBoost/LightGBM behind a `Forecaster` interface
  (`fit`/`predict`). **Time-based train/test split** — never random, no leakage.
- `explain_shap.py`: SHAP feature importance.
- `scripts/train_model.py`: BQ → features → split → train → evaluate → save
  `.joblib`.
- Report MAE/RMSE **against the baselines**, on a stated data window, printed
  and saved.

**Done when:** running `train_model.py` produces a model artifact, prints a
metrics table (model vs persistence vs seasonal-naive), and saves SHAP plots.

**Verify:** run the script; read the metrics; confirm the split is temporal;
confirm the baseline is honestly reported.

> **STOP — wait for review.**

---

### Phase 3 — OR-Tools repositioning planner

**Goal:** given imbalanced stations + a van fleet, produce feasible routes.

**Tasks:**
- `planner.py`: map surplus/deficit stations to pickup/dropoff nodes; solve a
  capacitated VRP with OR-Tools behind a `Planner` interface. Inputs: station
  imbalances, van capacity/count, time/shift budget.
- A `simulate_impact()` function: projected network health / lost trips under
  do-nothing vs the plan (feeds `evaluate_plan` node and the UI delta).
- Tests on small, hand-checkable instances (known optimal or known bound).

**Done when:** given a fixture imbalance, the planner returns valid routes
respecting capacities/budget, and `simulate_impact` returns a sensible delta.

**Verify:** run the planner on the fixture; eyeball routes for feasibility;
check the delta direction makes sense.

> **STOP — wait for review.**

---

### Phase 4 — LangGraph orchestration + human gate

**Goal:** wire Phases 1–3 into the graph from §6, with the re-plan loop and the
approval interrupt.

**Tasks:**
- `state.py`, `nodes.py` (wrapping data/ml/optim tools + the single Groq call
  in `explain`), `edges.py` (deterministic predicates), `graph.py`.
- Postgres/Supabase checkpointer for `interrupt()` persistence.
- `groq_client.py`: one structured, low-token explanation call + a deterministic
  fallback string if the LLM is unavailable.
- `plans` table in Supabase (see §14).
- `scripts/run_tick.py`: invoke one full graph tick.
- **Tests:**
  - idle tick → 0 LLM calls
  - triggered tick → exactly 1 LLM call
  - re-plan loop terminates at MAX
  - approve → dispatch persists a `plans` row
  - LLM unavailable → deterministic fallback, graph completes

**Done when:** a full tick runs end-to-end on live GBFS data, pauses at
approval, resumes on a supplied decision, and persists an approved plan.

**Verify:** run one tick; observe the pause; approve → confirm a `plans` row;
run an idle scenario → confirm 0 LLM calls.

> **STOP — wait for review.**

---

### Phase 5 — Operator console (Streamlit)

**Goal:** the dashboard from §9 — decision and value legible at a glance.

**Tasks:**
- `app.py` + all components from §9: KPI strip, pydeck map with now-vs-predicted
  toggle and route overlay, plan panel with before/after delta and approve/reject
  wired to the graph's interrupt, LLM work-order card, decision-trace strip,
  station×hour risk heatmap.
- Numbers shown must be real (from the model/solver), never hard-coded.
- Works on Streamlit Community Cloud with secrets in the platform.

**Done when:** the console renders live Citi Bike data, shows a real plan, and
an approval in the UI drives the graph to persist a plan.

**Verify:** open the app; trigger a plan; approve; confirm the map, delta,
trace, and heatmap reflect actual computed values.

> **STOP — wait for review.**

---

### Phase 6 — Deploy + document

**Goal:** public, reproducible, honestly documented.

**Tasks:**
- Deploy the console to Streamlit Community Cloud. Confirm the keepalive Action
  runs.
- Rewrite `README.md`: what it does, the honest metrics with baseline and
  window, architecture summary, live demo link, run instructions, screenshots.
  No overclaiming (§10).

**Done when:** a fresh reader can understand, run locally, and see the live demo;
every claimed number names its baseline and data window.

**Verify:** read the README as a stranger; follow the setup on a clean machine;
open the deployed app.

> **STOP — final review.**

---

## 13. .env template

```env
# Copy to .env and fill in. NEVER commit .env.

# --- Supabase (Frankfurt / eu-central) ---
SUPABASE_URL=
SUPABASE_KEY=

# --- LLM (Groq, free tier) ---
GROQ_API_KEY=

# --- GBFS ---
GBFS_PRIMARY_DISCOVERY_URL=https://gbfs.citibikenyc.com/gbfs/gbfs.json
GBFS_PRIMARY_SYSTEM_ID=citi-bike-nyc

# --- BigQuery (sandbox, no credentials needed for public datasets) ---
# google-cloud-bigquery can query public datasets without a service account.
# If you need explicit auth later: GOOGLE_APPLICATION_CREDENTIALS=path/to/key.json

# --- Weather (optional; Open-Meteo needs no key) ---
# OPEN_METEO_BASE_URL=https://api.open-meteo.com/v1/forecast

# --- Runtime ---
FORECAST_HORIZON_MIN=45
IMBALANCE_THRESHOLD=0.30
MAX_REPLAN=3
VAN_COUNT=2
VAN_CAPACITY=20
SHIFT_BUDGET_MIN=120
PG_WINDOW_HOURS=72
```

---

## 14. Supabase schema (tiny)

```sql
-- Station metadata (upserted from GBFS, ~2K rows)
CREATE TABLE stations (
    system_id   TEXT NOT NULL,
    station_id  TEXT NOT NULL,
    name        TEXT,
    lat         DOUBLE PRECISION,
    lon         DOUBLE PRECISION,
    capacity    INTEGER,
    PRIMARY KEY (system_id, station_id)
);

-- Persisted decisions (from the dispatch node)
CREATE TABLE plans (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    system_id        TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    tick_time        TIMESTAMPTZ NOT NULL,
    approval         TEXT NOT NULL,
    routes           JSONB NOT NULL,
    projected_impact JSONB,
    work_orders      TEXT,
    decision_trace   JSONB
);
```

The LangGraph Postgres checkpointer creates its own tables. No snapshot time
series in Postgres — all historical data is queried from BigQuery at training
time and held in memory at inference time.

---

## 15. environment.yml

```yaml
name: rebalancer
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pandas
  - numpy
  - scikit-learn
  - pip:
      # Pin exact versions after checking current stable releases in Phase 0.
      - pydantic-settings
      - python-dotenv
      - requests
      - supabase
      - google-cloud-bigquery
      - db-dtypes
      - xgboost
      - lightgbm
      - shap
      - ortools
      - langgraph
      - langgraph-checkpoint-postgres
      - groq
      - streamlit
      - pydeck
      - plotly
      - pytest
      - black
      - isort
      - ruff
```

---

## 16. Standing rules

- Small commits, clear messages, tests alongside code.
- No secrets in the repo, ever.
- If a phase reveals a needed decision not in §11, stop and ask. Once decided,
  append it to §11 before continuing.
- Every interface (Forecaster, Planner, DataClient, LLMClient) must have at
  least one concrete implementation and one test, before being wired into the
  graph.
- When in doubt, re-read this file. If a decision isn't written down, **STOP
  and ask Etienne** rather than guessing.
