"""LLM-generated driver work order card."""

import html

import streamlit as st


def render_work_order(state: dict) -> None:
    work_orders = state.get("work_orders", "")
    if not work_orders:
        return

    llm_calls = state.get("llm_calls", 0)
    badge_class = "llm" if llm_calls > 0 else "template"
    badge_label = "LLM" if llm_calls > 0 else "TEMPLATE"

    safe_text = html.escape(work_orders)

    st.markdown(
        f'<div class="work-order-card">'
        f'<div style="display:flex; align-items:center; justify-content:space-between; '
        f'margin-bottom:8px;">'
        f'<div class="section-header" style="margin-bottom:0; padding-bottom:0; border:none;">'
        f"Driver Work Order</div>"
        f'<span class="wo-badge {badge_class}">Source: {badge_label}</span>'
        f"</div>"
        f'<div class="wo-text">{safe_text}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
