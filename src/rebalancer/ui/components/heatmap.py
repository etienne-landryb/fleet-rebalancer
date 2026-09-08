"""Station risk heatmap: top 15 at-risk stations as horizontal bars."""

import plotly.graph_objects as go
import streamlit as st


def render_heatmap(state: dict) -> None:
    stations = state.get("stations", {})
    imbalance = state.get("imbalance", {})
    if not stations:
        return

    imbalanced = imbalance.get("stations", {})

    sorted_stations = sorted(
        imbalanced.items(),
        key=lambda x: x[1].get("fill", 0.5),
    )[:15]

    if not sorted_stations:
        st.markdown(
            '<div class="console-card" style="text-align:center; padding:24px;">'
            '<span style="color:var(--text-dim); font-family:var(--mono); font-size:13px;">'
            "No at-risk stations to display.</span></div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<div class="section-header">Station Risk Heatmap</div>', unsafe_allow_html=True
    )

    names = []
    fills = []
    for sid, info in reversed(sorted_stations):
        s = stations.get(sid, {})
        names.append(s.get("name", sid)[:30])
        fills.append(info.get("fill", 0.5))

    bar_colors = []
    for f in fills:
        if f <= 0.15:
            bar_colors.append("#ef4444")
        elif f >= 0.85:
            bar_colors.append("#3b82f6")
        else:
            bar_colors.append("#f59e0b")

    fig = go.Figure(
        go.Bar(
            x=fills,
            y=names,
            orientation="h",
            marker=dict(color=bar_colors),
            text=[f"{f:.0%}" for f in fills],
            textposition="outside",
            textfont=dict(family="JetBrains Mono, monospace", size=11, color="#9ca3af"),
            hovertemplate="<b>%{y}</b><br>Fill: %{x:.0%}<extra></extra>",
        )
    )

    fig.update_layout(
        xaxis_title=None,
        xaxis=dict(
            range=[0, 1.1],
            tickformat=".0%",
            color="#9ca3af",
            gridcolor="rgba(255,255,255,0.04)",
            tickfont=dict(family="JetBrains Mono, monospace", size=10),
        ),
        yaxis=dict(
            color="#9ca3af",
            tickfont=dict(family="JetBrains Mono, monospace", size=10),
        ),
        height=max(280, len(names) * 26),
        margin=dict(l=10, r=40, t=10, b=20),
        plot_bgcolor="#111827",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9ca3af"),
    )

    st.plotly_chart(fig, use_container_width=True)
