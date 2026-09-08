"""KPI strip: five metric cards with colored left borders."""

import streamlit as st


def render_kpi_strip(state: dict) -> None:
    stations = state.get("stations", {})
    imbalance = state.get("imbalance", {})
    impact = state.get("projected_impact", {})
    trigger = state.get("trigger", False)
    approval = state.get("approval", "")

    total = len(stations) or 1
    imbalanced_stations = imbalance.get("stations", {})
    starving = sum(
        1 for v in imbalanced_stations.values() if v.get("risk") == "starving"
    )
    saturated = sum(
        1 for v in imbalanced_stations.values() if v.get("risk") == "saturated"
    )
    healthy_pct = 1.0 - (starving + saturated) / total

    if approval == "approved":
        plan_status = "DISPATCHED"
    elif approval == "pending":
        plan_status = "PENDING"
    elif approval == "rejected":
        plan_status = "REJECTED"
    elif trigger:
        plan_status = "PLANNING"
    else:
        plan_status = "IDLE"

    bikes_moved = impact.get("bikes_moved", 0) if impact else 0

    health_color = (
        "green" if healthy_pct >= 0.7 else ("amber" if healthy_pct >= 0.5 else "red")
    )
    starving_color = "green" if starving == 0 else ("amber" if starving < 50 else "red")
    saturated_color = (
        "green" if saturated == 0 else ("amber" if saturated < 50 else "red")
    )
    bikes_color = "blue" if bikes_moved > 0 else "amber"
    status_color = {
        "DISPATCHED": "green",
        "PENDING": "amber",
        "REJECTED": "red",
        "PLANNING": "blue",
        "IDLE": "green",
    }.get(plan_status, "blue")

    cards = [
        ("Network Health", f"{healthy_pct:.0%}", health_color),
        ("Starving Stations", str(starving), starving_color),
        ("Saturated Stations", str(saturated), saturated_color),
        ("Bikes Moved", str(bikes_moved) if impact else "--", bikes_color),
        ("Plan Status", plan_status, status_color),
    ]

    cols = st.columns(5)
    for col, (label, value, color) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div class="kpi-card status-{color}">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )
