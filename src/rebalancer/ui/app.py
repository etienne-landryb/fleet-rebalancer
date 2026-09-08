"""Fleet Rebalancer -- Operator Console.

Run with:
    streamlit run src/rebalancer/ui/app.py
"""

import logging
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from rebalancer.config import get_settings
from rebalancer.data.gbfs_client import GBFSClient
from rebalancer.llm.groq_client import GroqClient, deterministic_fallback
from rebalancer.optim.planner import ORToolsPlanner, Station, simulate_impact
from rebalancer.ui.components.heatmap import render_heatmap
from rebalancer.ui.components.kpi_strip import render_kpi_strip
from rebalancer.ui.components.map_view import render_map
from rebalancer.ui.components.plan_panel import render_plan_panel
from rebalancer.ui.components.trace import render_trace
from rebalancer.ui.components.work_order import render_work_order

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Fleet Rebalancer",
    page_icon="🚲",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Global CSS — dark operations console theme
# ---------------------------------------------------------------------------
_THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg: #0a0e1a;
    --surface: #111827;
    --border: #1f2937;
    --healthy: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --primary: #3b82f6;
    --text: #f9fafb;
    --text-dim: #9ca3af;
    --mono: 'JetBrains Mono', 'Cascadia Code', 'Fira Code', monospace;
    --sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Main background */
[data-testid="stAppViewContainer"] { background-color: var(--bg) !important; }
[data-testid="stHeader"] { background-color: var(--bg) !important; }
[data-testid="stMainBlockContainer"] { max-width: 100% !important; padding: 1rem 2rem !important; }
html, body, [data-testid="stApp"] { background-color: var(--bg) !important; }

/* Hide default sidebar */
[data-testid="stSidebar"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* Typography */
h1, h2, h3, h4, h5, h6 { font-family: var(--sans) !important; color: var(--text) !important; }
p, span, label, div { color: var(--text); }
.stMarkdown { color: var(--text); }

/* Remove default metric styling */
[data-testid="stMetric"] { background: transparent !important; }
[data-testid="stMetricLabel"] { color: var(--text-dim) !important; }
[data-testid="stMetricValue"] { font-family: var(--mono) !important; color: var(--text) !important; }

/* Card container */
.console-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 8px;
}

/* KPI card */
.kpi-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    border-radius: 8px 0 0 8px;
}
.kpi-card.status-green::before { background: var(--healthy); }
.kpi-card.status-amber::before { background: var(--warning); }
.kpi-card.status-red::before { background: var(--danger); }
.kpi-card.status-blue::before { background: var(--primary); }

.kpi-label {
    font-family: var(--sans);
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim);
    margin-bottom: 4px;
}
.kpi-value {
    font-family: var(--mono);
    font-size: 28px;
    font-weight: 600;
    color: var(--text);
    line-height: 1.1;
}

/* Status bar */
.status-bar {
    display: flex;
    gap: 24px;
    align-items: center;
    padding: 8px 0;
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    margin-bottom: 16px;
}
.status-bar span { white-space: nowrap; }
.status-dot {
    display: inline-block;
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--healthy);
    margin-right: 6px;
}

/* Header row */
.header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 8px;
}
.header-title {
    font-family: var(--sans);
    font-size: 24px;
    font-weight: 700;
    color: var(--text);
    display: flex;
    align-items: center;
    gap: 10px;
}
.header-title .icon { font-size: 28px; }

/* Plan card styles */
.plan-metric-row {
    display: flex;
    gap: 12px;
    margin: 8px 0;
}
.plan-metric {
    flex: 1;
    background: rgba(255,255,255,0.03);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 12px;
    text-align: center;
}
.plan-metric .pm-label {
    font-family: var(--sans);
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-dim);
    margin-bottom: 2px;
}
.plan-metric .pm-value {
    font-family: var(--mono);
    font-size: 20px;
    font-weight: 600;
    color: var(--text);
}
.plan-metric .pm-delta {
    font-family: var(--mono);
    font-size: 12px;
    margin-top: 2px;
}
.pm-delta.positive { color: var(--healthy); }
.pm-delta.negative { color: var(--danger); }

/* Van assignment */
.van-stop {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text-dim);
    padding: 3px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.van-stop:last-child { border-bottom: none; }
.van-stop .action-pickup { color: var(--danger); font-weight: 600; }
.van-stop .action-dropoff { color: var(--healthy); font-weight: 600; }

/* Work order card */
.work-order-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px;
    margin-top: 12px;
}
.wo-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.wo-badge.llm { background: rgba(59,130,246,0.15); color: var(--primary); }
.wo-badge.template { background: rgba(156,163,175,0.15); color: var(--text-dim); }
.wo-text {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text-dim);
    white-space: pre-wrap;
    line-height: 1.6;
    margin-top: 10px;
    max-height: 200px;
    overflow-y: auto;
}

/* Trace pipeline */
.trace-pipeline {
    display: flex;
    align-items: center;
    gap: 0;
    flex-wrap: wrap;
    padding: 8px 0;
}
.trace-node {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    border-radius: 20px;
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 500;
    white-space: nowrap;
}
.trace-node.active {
    background: rgba(59,130,246,0.15);
    color: var(--primary);
    border: 1px solid rgba(59,130,246,0.3);
}
.trace-node.dim {
    background: rgba(255,255,255,0.03);
    color: #4b5563;
    border: 1px solid rgba(255,255,255,0.05);
}
.trace-arrow {
    color: #374151;
    font-size: 14px;
    padding: 0 2px;
    font-family: var(--mono);
}
.trace-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    border-radius: 6px;
    font-family: var(--mono);
    font-size: 11px;
    font-weight: 600;
    margin-left: 8px;
}
.trace-badge.llm-badge { background: rgba(245,158,11,0.12); color: var(--warning); }
.trace-badge.replan-badge { background: rgba(239,68,68,0.12); color: var(--danger); }

/* Banner */
.dispatch-banner {
    padding: 14px 20px;
    border-radius: 8px;
    font-family: var(--sans);
    font-size: 15px;
    font-weight: 600;
    margin: 8px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.dispatch-banner.approved {
    background: rgba(16,185,129,0.1);
    border: 1px solid rgba(16,185,129,0.3);
    color: var(--healthy);
}
.dispatch-banner.rejected {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.3);
    color: var(--danger);
}

/* Map legend */
.map-legend {
    display: flex;
    gap: 20px;
    padding: 8px 0 4px 0;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--text-dim);
}
.legend-dot {
    display: inline-block;
    width: 10px; height: 10px;
    border-radius: 50%;
    margin-right: 5px;
    vertical-align: middle;
}

/* Section header */
.section-header {
    font-family: var(--sans);
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-dim);
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border);
}

/* Button overrides */
[data-testid="stButton"] button[kind="primary"] {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    font-family: var(--sans) !important;
    font-weight: 600 !important;
}
[data-testid="stButton"] button[kind="secondary"] {
    background: transparent !important;
    color: var(--text-dim) !important;
    border: 1px solid var(--border) !important;
    font-family: var(--sans) !important;
}

/* Heatmap override */
.js-plotly-plot .plotly .modebar { display: none !important; }

/* Expander */
[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
}
[data-testid="stExpander"] summary span {
    font-family: var(--mono) !important;
    font-size: 12px !important;
    color: var(--text-dim) !important;
}

/* Info boxes */
.stAlert { background: var(--surface) !important; border: 1px solid var(--border) !important; }

/* Divider */
[data-testid="stHorizontalBlock"] { gap: 12px !important; }
hr { border-color: var(--border) !important; }
</style>
"""


def _init_state() -> None:
    defaults = {
        "tick_time": None,
        "system_id": "",
        "stations": {},
        "forecast": {},
        "imbalance": {},
        "trigger": False,
        "fleet": {},
        "constraints": {},
        "plan": [],
        "plan_feasible": False,
        "replan_count": 0,
        "projected_impact": {},
        "approval": "",
        "work_orders": "",
        "decision_trace": [],
        "llm_calls": 0,
        "tick_complete": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _get_state() -> dict:
    keys = [
        "tick_time",
        "system_id",
        "stations",
        "forecast",
        "imbalance",
        "trigger",
        "fleet",
        "constraints",
        "plan",
        "plan_feasible",
        "replan_count",
        "projected_impact",
        "approval",
        "work_orders",
        "decision_trace",
        "llm_calls",
    ]
    return {k: st.session_state.get(k) for k in keys}


def _run_ingest() -> None:
    settings = get_settings()
    gbfs = GBFSClient(
        discovery_url=settings.gbfs_primary_discovery_url,
        system_id=settings.gbfs_primary_system_id,
    )
    info_list = gbfs.fetch_station_information()
    status_list = gbfs.fetch_station_status()

    status_map = {s.station_id: s for s in status_list}
    stations = {}
    for info in info_list:
        status = status_map.get(info.station_id)
        if status is None:
            continue
        stations[info.station_id] = {
            "station_id": info.station_id,
            "name": info.name,
            "lat": info.lat,
            "lon": info.lon,
            "capacity": info.capacity,
            "num_bikes_available": status.num_bikes_available,
            "num_docks_available": status.num_docks_available,
            "is_renting": status.is_renting,
            "is_returning": status.is_returning,
        }

    st.session_state["stations"] = stations
    st.session_state["tick_time"] = datetime.now(timezone.utc)
    st.session_state["system_id"] = settings.gbfs_primary_system_id
    st.session_state["decision_trace"] = ["ingest"]
    st.session_state["llm_calls"] = 0


def _run_forecast() -> None:
    stations = st.session_state["stations"]
    forecast_data = {}
    for sid, s in stations.items():
        forecast_data[sid] = {"predicted_bikes": s["num_bikes_available"]}
    st.session_state["forecast"] = forecast_data
    st.session_state["decision_trace"].append("forecast")


def _run_assess() -> None:
    settings = get_settings()
    stations = st.session_state["stations"]
    forecast_data = st.session_state["forecast"]
    threshold = settings.imbalance_threshold

    imbalance_data: dict = {"stations": {}, "aggregate": 0.0}
    starving = 0
    saturated = 0

    for sid, s in stations.items():
        capacity = s.get("capacity", 1) or 1
        predicted = forecast_data.get(sid, {}).get(
            "predicted_bikes", s["num_bikes_available"]
        )
        fill = predicted / capacity
        if fill <= 0.15:
            starving += 1
            imbalance_data["stations"][sid] = {"risk": "starving", "fill": fill}
        elif fill >= 0.85:
            saturated += 1
            imbalance_data["stations"][sid] = {"risk": "saturated", "fill": fill}

    total = len(stations) or 1
    aggregate = (starving + saturated) / total
    imbalance_data["aggregate"] = aggregate
    trigger = aggregate >= threshold

    st.session_state["imbalance"] = imbalance_data
    st.session_state["trigger"] = trigger
    st.session_state["decision_trace"].append("assess_imbalance")


def _run_plan() -> None:
    settings = get_settings()
    stations_data = st.session_state["stations"]
    forecast_data = st.session_state["forecast"]
    constraints = st.session_state.get("constraints", {})

    van_count = constraints.get("van_count", settings.van_count)
    van_capacity = constraints.get("van_capacity", settings.van_capacity)
    shift_budget = constraints.get("shift_budget_min", settings.shift_budget_min)

    station_objects = []
    for sid, s in stations_data.items():
        predicted = forecast_data.get(sid, {}).get(
            "predicted_bikes", s["num_bikes_available"]
        )
        station_objects.append(
            Station(
                station_id=sid,
                name=s["name"],
                lat=s["lat"],
                lon=s["lon"],
                capacity=s.get("capacity", 1),
                current_bikes=s["num_bikes_available"],
                predicted_bikes=predicted,
            )
        )

    planner = ORToolsPlanner()
    result = planner.solve(
        stations=station_objects,
        van_count=van_count,
        van_capacity=van_capacity,
        shift_budget_min=shift_budget,
    )

    routes_data = []
    for route in result.routes:
        routes_data.append(
            {
                "van_id": route.van_id,
                "stops": [asdict(s) for s in route.stops],
                "total_pickups": route.total_pickups,
                "total_dropoffs": route.total_dropoffs,
                "distance_km": route.distance_km,
                "duration_min": route.duration_min,
            }
        )

    impact = simulate_impact(station_objects, result)

    st.session_state["plan"] = routes_data
    st.session_state["plan_feasible"] = result.feasible and len(result.routes) > 0
    st.session_state["projected_impact"] = asdict(impact)
    st.session_state["decision_trace"].append("plan")


def _run_evaluate() -> None:
    impact = st.session_state.get("projected_impact", {})
    feasible = st.session_state.get("plan_feasible", False)
    improving = impact.get("health_improvement", 0) > 0
    st.session_state["plan_feasible"] = feasible and improving
    st.session_state["decision_trace"].append("evaluate_plan")


def _run_explain() -> None:
    settings = get_settings()
    plan_lines = []
    for route_data in st.session_state.get("plan", []):
        van_id = route_data.get("van_id", "?")
        plan_lines.append(f"Van {van_id}:")
        for stop in route_data.get("stops", []):
            plan_lines.append(
                f"  {stop['action'].upper()} {stop['quantity']} bikes "
                f"@ {stop['name']}"
            )
    plan_summary = "\n".join(plan_lines) or "No routes."

    impact = st.session_state.get("projected_impact", {})
    impact_summary = (
        f"Network health: {impact.get('do_nothing_health', 0):.0%} -> "
        f"{impact.get('planned_health', 0):.0%}\n"
        f"Starving: {impact.get('do_nothing_starving', 0)} -> "
        f"{impact.get('planned_starving', 0)}\n"
        f"Saturated: {impact.get('do_nothing_saturated', 0)} -> "
        f"{impact.get('planned_saturated', 0)}\n"
        f"Bikes moved: {impact.get('bikes_moved', 0)}"
    )

    if settings.groq_api_key:
        try:
            client = GroqClient(
                api_key=settings.groq_api_key, model=settings.groq_model
            )
            work_orders = client.explain(plan_summary, impact_summary)
            st.session_state["llm_calls"] = st.session_state.get("llm_calls", 0) + 1
        except Exception:
            work_orders = ""
    else:
        work_orders = ""

    if not work_orders:
        work_orders = deterministic_fallback(plan_summary, impact_summary)

    st.session_state["work_orders"] = work_orders
    st.session_state["approval"] = "pending"
    st.session_state["decision_trace"].append("explain")


def _run_dispatch() -> None:
    settings = get_settings()
    plan_data = {
        "system_id": st.session_state.get("system_id", ""),
        "tick_time": st.session_state.get(
            "tick_time", datetime.now(timezone.utc)
        ).isoformat(),
        "approval": st.session_state.get("approval", "approved"),
        "routes": st.session_state.get("plan", []),
        "projected_impact": st.session_state.get("projected_impact", {}),
        "work_orders": st.session_state.get("work_orders", ""),
        "decision_trace": st.session_state.get("decision_trace", []),
    }

    if settings.supabase_url and settings.supabase_key:
        try:
            from rebalancer.data.supabase_client import SupabaseClient

            sb = SupabaseClient(url=settings.supabase_url, key=settings.supabase_key)
            sb.insert_plan(plan_data)
            logger.info("Plan dispatched to Supabase")
        except Exception as exc:
            logger.warning("Failed to persist plan: %s", exc)

    st.session_state["decision_trace"].append("dispatch")


def _run_tick() -> None:
    _run_ingest()
    _run_forecast()
    _run_assess()

    if not st.session_state["trigger"]:
        st.session_state["tick_complete"] = True
        return

    _run_plan()
    _run_evaluate()

    if st.session_state["plan_feasible"]:
        _run_explain()
    else:
        settings = get_settings()
        for attempt in range(settings.max_replan):
            constraints = dict(st.session_state.get("constraints", {}))
            replan_count = st.session_state.get("replan_count", 0) + 1
            constraints["van_count"] = (
                constraints.get("van_count", settings.van_count) + 1
            )
            constraints["shift_budget_min"] = (
                constraints.get("shift_budget_min", settings.shift_budget_min) + 30
            )
            st.session_state["constraints"] = constraints
            st.session_state["replan_count"] = replan_count
            st.session_state["decision_trace"].append(
                f"relax_constraints (attempt {replan_count})"
            )
            _run_plan()
            _run_evaluate()
            if st.session_state["plan_feasible"]:
                break
        _run_explain()

    st.session_state["tick_complete"] = True


def main() -> None:
    _init_state()

    # Inject theme CSS
    st.markdown(_THEME_CSS, unsafe_allow_html=True)

    # --- Header row: title + Run Tick button ---
    hdr_left, hdr_right = st.columns([4, 1])
    with hdr_left:
        st.markdown(
            '<div class="header-title">'
            '<span class="icon">&#x1F6B2;</span> Fleet Rebalancer'
            "</div>",
            unsafe_allow_html=True,
        )
    with hdr_right:
        run_clicked = st.button("Run Tick", type="primary", use_container_width=True)

    if run_clicked:
        for key in list(st.session_state.keys()):
            if key not in ("_init",):
                del st.session_state[key]
        _init_state()
        with st.spinner("Running graph tick..."):
            _run_tick()
        st.rerun()

    # --- Status bar ---
    settings = get_settings()
    tick_time = st.session_state.get("tick_time")
    tick_str = tick_time.strftime("%H:%M:%S UTC") if tick_time else "--:--:--"
    st.markdown(
        f'<div class="status-bar">'
        f'<span><span class="status-dot"></span>{settings.gbfs_primary_system_id}</span>'
        f"<span>Threshold: {settings.imbalance_threshold:.0%}</span>"
        f"<span>Fleet: {settings.van_count} vans x {settings.van_capacity}</span>"
        f"<span>Shift: {settings.shift_budget_min} min</span>"
        f"<span>Last tick: {tick_str}</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    state = _get_state()

    if not state.get("stations"):
        st.markdown(
            '<div style="text-align:center; padding:80px 0; color:var(--text-dim);">'
            '<p style="font-size:48px; margin-bottom:16px;">&#x1F6B2;</p>'
            '<p style="font-family:var(--sans); font-size:16px;">'
            "Press <b>Run Tick</b> to ingest live data and run the rebalancer."
            "</p></div>",
            unsafe_allow_html=True,
        )
        return

    # --- 1. KPI strip ---
    render_kpi_strip(state)

    # --- Dispatch banner (if decided) ---
    approval = state.get("approval", "")
    impact = state.get("projected_impact", {})
    plan = state.get("plan", [])

    if approval == "approved":
        bikes = impact.get("bikes_moved", 0)
        vans = len(plan)
        st.markdown(
            f'<div class="dispatch-banner approved">'
            f'&#x2713; Plan dispatched &mdash; {vans} van{"s" if vans != 1 else ""}, '
            f"{bikes} bikes repositioned.</div>",
            unsafe_allow_html=True,
        )
    elif approval == "rejected":
        st.markdown(
            '<div class="dispatch-banner rejected">' "&#x2717; Plan rejected.</div>",
            unsafe_allow_html=True,
        )

    # --- 2. Map (60%) + 3. Plan / Work Order (40%) ---
    col_map, col_plan = st.columns([3, 2])

    with col_map:
        st.markdown(
            '<div class="section-header">Station Health Map</div>',
            unsafe_allow_html=True,
        )
        render_map(state)

    with col_plan:
        if approval not in ("approved", "rejected"):
            st.markdown(
                '<div class="section-header">Recommended Plan</div>',
                unsafe_allow_html=True,
            )
            decision = render_plan_panel(state)
            if decision:
                st.session_state["approval"] = decision
                st.session_state["decision_trace"].append(f"human_approval: {decision}")
                if decision == "approved":
                    _run_dispatch()
                st.rerun()
        render_work_order(state)

    # --- 4. Trace (50%) + 5. Heatmap (50%) ---
    col_trace, col_heat = st.columns([1, 1])

    with col_trace:
        render_trace(state)

    with col_heat:
        render_heatmap(state)


if __name__ == "__main__":
    main()
