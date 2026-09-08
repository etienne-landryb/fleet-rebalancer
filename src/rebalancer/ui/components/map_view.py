"""Station health map: pydeck dark basemap, station dots, route overlay."""

import pydeck as pdk
import streamlit as st

_DARK_MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"


def _station_color(fill: float, risk: str) -> list[int]:
    if risk == "starving":
        return [239, 68, 68, 220]
    elif risk == "saturated":
        return [59, 130, 246, 220]
    return [16, 185, 129, 200]


def _build_station_layer(stations: dict, imbalance: dict) -> pdk.Layer:
    imbalanced = imbalance.get("stations", {})
    data = []
    for sid, s in stations.items():
        capacity = s.get("capacity", 1) or 1
        fill = s["num_bikes_available"] / capacity
        risk = imbalanced.get(sid, {}).get("risk", "healthy")
        data.append(
            {
                "position": [s["lon"], s["lat"]],
                "color": _station_color(fill, risk),
                "radius": max(25, min(70, capacity * 1.5)),
                "name": s["name"],
                "bikes": s["num_bikes_available"],
                "capacity": capacity,
                "fill_pct": f"{fill:.0%}",
                "risk": risk,
            }
        )

    return pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="position",
        get_color="color",
        get_radius="radius",
        pickable=True,
        opacity=0.85,
    )


def _build_route_layer(plan: list, stations: dict) -> pdk.Layer | None:
    paths = []
    colors = [
        [245, 158, 11, 220],
        [168, 85, 247, 220],
        [14, 165, 233, 220],
        [236, 72, 153, 220],
    ]
    for route in plan:
        van_id = route.get("van_id", 0)
        color = colors[van_id % len(colors)]
        path_coords = []
        for stop in route.get("stops", []):
            sid = stop["station_id"]
            s = stations.get(sid)
            if s:
                path_coords.append([s["lon"], s["lat"]])
        if len(path_coords) >= 2:
            paths.append({"path": path_coords, "color": color, "van_id": van_id})

    if not paths:
        return None

    return pdk.Layer(
        "PathLayer",
        data=paths,
        get_path="path",
        get_color="color",
        width_min_pixels=3,
        width_max_pixels=6,
        pickable=True,
    )


def render_map(state: dict) -> None:
    stations = state.get("stations", {})
    if not stations:
        st.info("No station data loaded yet.")
        return

    imbalance = state.get("imbalance", {})
    plan = state.get("plan", [])

    lats = [s["lat"] for s in stations.values()]
    lons = [s["lon"] for s in stations.values()]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)

    layers = [_build_station_layer(stations, imbalance)]
    route_layer = _build_route_layer(plan, stations)
    if route_layer:
        layers.append(route_layer)

    view = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=11,
        pitch=0,
    )

    tooltip = {
        "html": (
            "<div style='font-family:JetBrains Mono,monospace;font-size:12px;'>"
            "<b>{name}</b><br/>"
            "Bikes: {bikes}/{capacity} ({fill_pct})<br/>"
            "Status: {risk}"
            "</div>"
        ),
        "style": {
            "backgroundColor": "#111827",
            "color": "#f9fafb",
            "fontSize": "12px",
            "border": "1px solid #1f2937",
            "borderRadius": "6px",
        },
    }

    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view,
            tooltip=tooltip,
            map_style=_DARK_MAP_STYLE,
        ),
        use_container_width=True,
        height=500,
    )

    st.markdown(
        '<div class="map-legend">'
        '<span><span class="legend-dot" style="background:#ef4444;"></span>Starving (&le;15%)</span>'
        '<span><span class="legend-dot" style="background:#10b981;"></span>Healthy</span>'
        '<span><span class="legend-dot" style="background:#3b82f6;"></span>Saturated (&ge;85%)</span>'
        '<span><span class="legend-dot" style="background:#f59e0b;"></span>Van route</span>'
        "</div>",
        unsafe_allow_html=True,
    )
