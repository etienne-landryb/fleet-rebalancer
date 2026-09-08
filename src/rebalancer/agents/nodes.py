import logging
import os
from dataclasses import asdict
from datetime import datetime, timezone

from langgraph.types import interrupt

from rebalancer.agents.state import RebalanceState
from rebalancer.config import get_settings
from rebalancer.data.gbfs_client import GBFSClient
from rebalancer.llm.groq_client import GroqClient, deterministic_fallback
from rebalancer.optim.planner import (
    ORToolsPlanner,
    Station,
    simulate_impact,
)

logger = logging.getLogger(__name__)


def _format_plan_summary(state: RebalanceState) -> str:
    lines = []
    for route_data in state.get("plan", []):
        van_id = route_data.get("van_id", "?")
        lines.append(f"Van {van_id}:")
        for stop in route_data.get("stops", []):
            lines.append(
                f"  {stop['action'].upper()} {stop['quantity']} bikes "
                f"@ {stop['name']} ({stop['station_id']})"
            )
    return "\n".join(lines) if lines else "No routes."


def _format_impact_summary(state: RebalanceState) -> str:
    impact = state.get("projected_impact", {})
    if not impact:
        return "No impact data."
    return (
        f"Network health: {impact.get('do_nothing_health', 0):.0%} → "
        f"{impact.get('planned_health', 0):.0%} "
        f"(+{impact.get('health_improvement', 0):.0%})\n"
        f"Starving stations: {impact.get('do_nothing_starving', 0)} → "
        f"{impact.get('planned_starving', 0)}\n"
        f"Saturated stations: {impact.get('do_nothing_saturated', 0)} → "
        f"{impact.get('planned_saturated', 0)}\n"
        f"Bikes moved: {impact.get('bikes_moved', 0)}"
    )


def ingest(state: RebalanceState) -> dict:
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

    logger.info("Ingested %d stations", len(stations))
    return {
        "stations": stations,
        "tick_time": datetime.now(timezone.utc),
        "system_id": settings.gbfs_primary_system_id,
        "decision_trace": ["ingest"],
        "llm_calls": 0,
    }


def forecast(state: RebalanceState) -> dict:
    settings = get_settings()
    stations = state.get("stations", {})
    system_id = state.get("system_id", settings.gbfs_primary_system_id)

    forecast_method = "persistence_baseline"
    if system_id == "citi-bike-nyc" or system_id == "citi_bike_nyc":
        try:
            model_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "models",
                "xgboost_demand.joblib",
            )
            if os.path.exists(model_path):
                forecast_method = "xgboost"
                logger.info("XGBoost model loaded for %s", system_id)
            else:
                logger.info(
                    "No XGBoost model found at %s, using persistence baseline",
                    model_path,
                )
        except Exception as exc:
            logger.warning("Failed to load XGBoost model: %s", exc)

    forecast_data = {}
    for sid, s in stations.items():
        forecast_data[sid] = {
            "predicted_bikes": s["num_bikes_available"],
        }

    trace = list(state.get("decision_trace", []))
    trace.append("forecast")
    return {
        "forecast": forecast_data,
        "decision_trace": trace,
        "forecast_method": forecast_method,
    }


def assess_imbalance(state: RebalanceState) -> dict:
    settings = get_settings()
    stations = state.get("stations", {})
    forecast_data = state.get("forecast", {})
    threshold = settings.imbalance_threshold

    total_stations = len(stations)
    stations_with_inventory = sum(
        1
        for s in stations.values()
        if s.get("num_bikes_available", 0) > 0 or s.get("num_docks_available", 0) > 0
    )
    if total_stations >= 10 and stations_with_inventory < 5:
        trace = list(state.get("decision_trace", []))
        trace.append("assess_imbalance")
        logger.warning(
            "Only %d stations with non-zero inventory — feed may be initializing",
            stations_with_inventory,
        )
        return {
            "imbalance": {
                "stations": {},
                "aggregate": 0.0,
                "warning": (
                    "Insufficient station data — all stations report"
                    " zero inventory. Feed may be initializing."
                ),
            },
            "trigger": False,
            "decision_trace": trace,
        }

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

    trace = list(state.get("decision_trace", []))
    trace.append("assess_imbalance")

    logger.info(
        "Imbalance: %.1f%% (starving=%d, saturated=%d, trigger=%s)",
        aggregate * 100,
        starving,
        saturated,
        trigger,
    )
    return {
        "imbalance": imbalance_data,
        "trigger": trigger,
        "decision_trace": trace,
    }


def plan(state: RebalanceState) -> dict:
    settings = get_settings()
    stations_data = state.get("stations", {})
    forecast_data = state.get("forecast", {})
    constraints = state.get("constraints", {})

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

    trace = list(state.get("decision_trace", []))
    trace.append("plan")
    return {
        "plan": routes_data,
        "plan_feasible": result.feasible and len(result.routes) > 0,
        "projected_impact": asdict(impact),
        "decision_trace": trace,
    }


def evaluate_plan(state: RebalanceState) -> dict:
    trace = list(state.get("decision_trace", []))
    trace.append("evaluate_plan")

    impact = state.get("projected_impact", {})
    feasible = state.get("plan_feasible", False)
    improving = impact.get("health_improvement", 0) > 0

    return {
        "plan_feasible": feasible and improving,
        "decision_trace": trace,
    }


def relax_constraints(state: RebalanceState) -> dict:
    settings = get_settings()
    constraints = dict(state.get("constraints", {}))
    replan_count = state.get("replan_count", 0) + 1

    constraints["van_count"] = constraints.get("van_count", settings.van_count) + 1
    constraints["shift_budget_min"] = (
        constraints.get("shift_budget_min", settings.shift_budget_min) + 30
    )

    trace = list(state.get("decision_trace", []))
    trace.append(f"relax_constraints (attempt {replan_count})")

    logger.info(
        "Relaxing constraints: van_count=%d, shift_budget=%d",
        constraints["van_count"],
        constraints["shift_budget_min"],
    )
    return {
        "constraints": constraints,
        "replan_count": replan_count,
        "decision_trace": trace,
    }


def explain(state: RebalanceState) -> dict:
    settings = get_settings()
    plan_summary = _format_plan_summary(state)
    impact_summary = _format_impact_summary(state)

    if settings.groq_api_key:
        client = GroqClient(api_key=settings.groq_api_key, model=settings.groq_model)
        work_orders = client.explain(plan_summary, impact_summary)
        llm_calls = state.get("llm_calls", 0) + 1
    else:
        work_orders = deterministic_fallback(plan_summary, impact_summary)
        llm_calls = state.get("llm_calls", 0)

    trace = list(state.get("decision_trace", []))
    trace.append("explain")
    return {
        "work_orders": work_orders,
        "approval": "pending",
        "llm_calls": llm_calls,
        "decision_trace": trace,
    }


def human_approval(state: RebalanceState) -> dict:
    plan_summary = _format_plan_summary(state)
    impact_summary = _format_impact_summary(state)
    work_orders = state.get("work_orders", "")

    decision = interrupt(
        {
            "plan": plan_summary,
            "impact": impact_summary,
            "work_orders": work_orders,
            "message": "Review the plan and approve or reject.",
        }
    )

    approval = "approved" if decision == "approved" else "rejected"
    trace = list(state.get("decision_trace", []))
    trace.append(f"human_approval: {approval}")
    return {"approval": approval, "decision_trace": trace}


def dispatch(state: RebalanceState) -> dict:
    trace = list(state.get("decision_trace", []))
    trace.append("dispatch")

    plan_data = {
        "system_id": state.get("system_id", ""),
        "tick_time": state.get("tick_time", datetime.now(timezone.utc)).isoformat(),
        "approval": state.get("approval", "approved"),
        "routes": state.get("plan", []),
        "projected_impact": state.get("projected_impact", {}),
        "work_orders": state.get("work_orders", ""),
        "decision_trace": trace,
    }

    settings = get_settings()
    if settings.supabase_url and settings.supabase_key:
        try:
            from rebalancer.data.supabase_client import SupabaseClient

            sb = SupabaseClient(url=settings.supabase_url, key=settings.supabase_key)
            sb.insert_plan(plan_data)
            logger.info("Dispatched plan to Supabase")
        except Exception as exc:
            logger.warning("Failed to persist plan to Supabase: %s", exc)
    else:
        logger.info("Supabase not configured — plan not persisted")

    return {"decision_trace": trace}
