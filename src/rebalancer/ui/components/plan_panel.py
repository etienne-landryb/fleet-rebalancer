"""Plan panel: before/after delta, van assignments, approve/reject."""

import streamlit as st


def render_plan_panel(state: dict) -> str | None:
    plan = state.get("plan", [])
    impact = state.get("projected_impact", {})
    approval = state.get("approval", "")

    if not plan:
        st.markdown(
            '<div class="console-card" style="text-align:center; padding:32px;">'
            '<span style="color:var(--text-dim); font-family:var(--mono); font-size:13px;">'
            "No plan generated this tick."
            "</span></div>",
            unsafe_allow_html=True,
        )
        return None

    health_after = impact.get("planned_health", 0)
    health_delta = impact.get("health_improvement", 0)
    starving_before = impact.get("do_nothing_starving", 0)
    starving_after = impact.get("planned_starving", 0)
    saturated_before = impact.get("do_nothing_saturated", 0)
    saturated_after = impact.get("planned_saturated", 0)

    delta_health_class = "positive" if health_delta > 0 else "negative"
    delta_starving = starving_after - starving_before
    delta_starving_class = "positive" if delta_starving < 0 else "negative"
    delta_saturated = saturated_after - saturated_before
    delta_saturated_class = "positive" if delta_saturated < 0 else "negative"

    st.markdown(
        '<div class="console-card">'
        '<div class="plan-metric-row">'
        '<div class="plan-metric">'
        '  <div class="pm-label">Network Health</div>'
        f'  <div class="pm-value">{health_after:.0%}</div>'
        f'  <div class="pm-delta {delta_health_class}">'
        f'    {"+" if health_delta > 0 else ""}{health_delta:.1%}</div>'
        "</div>"
        '<div class="plan-metric">'
        '  <div class="pm-label">Starving</div>'
        f'  <div class="pm-value">{starving_after}</div>'
        f'  <div class="pm-delta {delta_starving_class}">'
        f'    {"+" if delta_starving > 0 else ""}{delta_starving}</div>'
        "</div>"
        '<div class="plan-metric">'
        '  <div class="pm-label">Saturated</div>'
        f'  <div class="pm-value">{saturated_after}</div>'
        f'  <div class="pm-delta {delta_saturated_class}">'
        f'    {"+" if delta_saturated > 0 else ""}{delta_saturated}</div>'
        "</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )

    for route in plan:
        van_id = route.get("van_id", "?")
        stops = route.get("stops", [])
        dist = route.get("distance_km", 0)
        dur = route.get("duration_min", 0)
        with st.expander(
            f"Van {van_id} -- {len(stops)} stops, {dist:.1f} km, {dur:.0f} min",
            expanded=False,
        ):
            for stop in stops:
                action = stop["action"]
                action_class = (
                    "action-dropoff" if action == "dropoff" else "action-pickup"
                )
                st.markdown(
                    f'<div class="van-stop">'
                    f'<span class="{action_class}">{action.upper()}</span> '
                    f'{stop["quantity"]} bikes @ {stop["name"]}'
                    f"</div>",
                    unsafe_allow_html=True,
                )

    if approval == "pending":
        col_a, col_r = st.columns(2)
        with col_a:
            if st.button("Approve Plan", type="primary", use_container_width=True):
                return "approved"
        with col_r:
            if st.button("Reject Plan", type="secondary", use_container_width=True):
                return "rejected"

    return None
