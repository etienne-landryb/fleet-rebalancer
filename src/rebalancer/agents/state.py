from datetime import datetime
from typing import Any, Literal, TypedDict


class RebalanceState(TypedDict, total=False):
    tick_time: datetime
    system_id: str
    stations: dict[str, Any]
    forecast: dict[str, Any]
    imbalance: dict[str, Any]
    trigger: bool
    fleet: dict[str, Any]
    constraints: dict[str, Any]
    plan: list[Any]
    plan_feasible: bool
    replan_count: int
    projected_impact: dict[str, Any]
    approval: Literal["pending", "approved", "rejected"]
    work_orders: str
    decision_trace: list[str]
    llm_calls: int
    forecast_method: str
