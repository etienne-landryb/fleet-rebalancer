"""Decision trace: horizontal node pipeline with pills and badges."""

import streamlit as st

_ALL_NODES = [
    "ingest",
    "forecast",
    "assess_imbalance",
    "plan",
    "evaluate_plan",
    "explain",
    "human_approval",
    "dispatch",
]

_NODE_LABELS = {
    "ingest": "INGEST",
    "forecast": "FORECAST",
    "assess_imbalance": "ASSESS",
    "plan": "PLAN",
    "evaluate_plan": "EVALUATE",
    "explain": "EXPLAIN",
    "human_approval": "APPROVAL",
    "dispatch": "DISPATCH",
}

_NODE_ICONS = {
    "ingest": "&#x1F4E1;",
    "forecast": "&#x1F4C8;",
    "assess_imbalance": "&#x2696;",
    "plan": "&#x1F5FA;",
    "evaluate_plan": "&#x2705;",
    "explain": "&#x1F4AC;",
    "human_approval": "&#x1F464;",
    "dispatch": "&#x1F680;",
}


def render_trace(state: dict) -> None:
    trace = state.get("decision_trace", [])
    llm_calls = state.get("llm_calls", 0)
    trigger = state.get("trigger", False)
    replan_count = state.get("replan_count", 0)

    if not trace:
        st.markdown(
            '<div class="console-card" style="text-align:center; padding:24px;">'
            '<span style="color:var(--text-dim); font-family:var(--mono); font-size:13px;">'
            "No decision trace yet.</span></div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div class="section-header">Decision Trace</div>', unsafe_allow_html=True
    )

    active_bases = set()
    for step in trace:
        base = step.split("(")[0].split(":")[0].strip()
        active_bases.add(base)
        if "human_approval" in step:
            active_bases.add("human_approval")

    pills_html = []
    for node in _ALL_NODES:
        is_active = node in active_bases
        css_class = "active" if is_active else "dim"
        icon = _NODE_ICONS.get(node, "")
        label = _NODE_LABELS.get(node, node.upper())
        pills_html.append(f'<span class="trace-node {css_class}">{icon} {label}</span>')

    pipeline_html = '<span class="trace-arrow">&#x25B8;</span>'.join(pills_html)

    badges_html = (
        f'<span class="trace-badge llm-badge">LLM: {llm_calls}</span>'
        f'<span class="trace-badge replan-badge">Re-plans: {replan_count}</span>'
    )

    st.markdown(
        f'<div class="console-card">'
        f'<div class="trace-pipeline">{pipeline_html}{badges_html}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )

    if not trigger:
        st.markdown(
            '<div style="font-family:var(--mono); font-size:11px; color:var(--text-dim); '
            'padding:4px 0;">Idle tick: imbalance below threshold, no plan needed.</div>',
            unsafe_allow_html=True,
        )
