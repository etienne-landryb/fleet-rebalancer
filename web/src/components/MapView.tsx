"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMapGL, { Layer, Popup, Source } from "react-map-gl/mapbox";
import type { MapRef } from "react-map-gl/mapbox";
import "mapbox-gl/dist/mapbox-gl.css";
import type { LineString } from "geojson";
import { RefreshCw } from "lucide-react";
import type { Route, Station, Stop, ThemeMode } from "@/lib/types";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

type StationFilter = "all" | "starving" | "saturated" | "healthy";

const VAN_COLORS = [
  '#ef4444', // Van 1  — red
  '#22d3ee', // Van 2  — cyan
  '#a3e635', // Van 3  — lime
  '#f97316', // Van 4  — orange
  '#8b5cf6', // Van 5  — violet
  '#ec4899', // Van 6  — hot pink
  '#14b8a6', // Van 7  — teal
  '#fb923c', // Van 8  — light orange
  '#60a5fa', // Van 9  — light blue
  '#e879f9', // Van 10 — magenta
];

const MAP_STYLES: Record<ThemeMode, string> = {
  dark: "mapbox://styles/mapbox/dark-v11",
  light: "mapbox://styles/mapbox/streets-v12",
  system: "mapbox://styles/mapbox/navigation-night-v1",
};

interface StationGeoJson {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      station_id: string;
      name: string;
      capacity: number;
      bikes: number;
      docks: number;
      fill: number;
      risk: string;
    };
  }>;
}

function stationsToGeoJson(stations: Station[]): StationGeoJson {
  return {
    type: "FeatureCollection",
    features: stations.map((s) => ({
      type: "Feature" as const,
      geometry: {
        type: "Point" as const,
        coordinates: [s.lon, s.lat] as [number, number],
      },
      properties: {
        station_id: s.station_id,
        name: s.name,
        capacity: s.capacity,
        bikes: s.num_bikes_available,
        docks: s.num_docks_available,
        fill: s.fill_level,
        risk: s.risk,
      },
    })),
  };
}

const FILTER_BUTTONS: { value: StationFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "starving", label: "Starving" },
  { value: "healthy", label: "Healthy" },
  { value: "saturated", label: "Saturated" },
];

async function fetchChunkGeometry(stops: Stop[]): Promise<number[][] | null> {
  const coords = stops.map((s) => `${s.lon},${s.lat}`).join(";");
  const url = `https://api.mapbox.com/directions/v5/mapbox/driving/${coords}?geometries=geojson&overview=full&access_token=${MAPBOX_TOKEN}`;
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    const data = await res.json();
    return data.routes?.[0]?.geometry?.coordinates ?? null;
  } catch {
    return null;
  }
}

const MAX_WAYPOINTS = 25;

async function fetchRouteGeometry(stops: Stop[]): Promise<LineString | null> {
  if (stops.length < 2) return null;
  if (stops.length <= MAX_WAYPOINTS) {
    const coords = await fetchChunkGeometry(stops);
    if (!coords) return null;
    return { type: "LineString", coordinates: coords };
  }
  const allCoords: number[][] = [];
  for (let i = 0; i < stops.length; i += MAX_WAYPOINTS - 1) {
    const chunk = stops.slice(i, i + MAX_WAYPOINTS);
    if (chunk.length < 2) break;
    const coords = await fetchChunkGeometry(chunk);
    if (!coords) return null;
    if (allCoords.length > 0) coords.shift();
    allCoords.push(...coords);
  }
  if (allCoords.length === 0) return null;
  return { type: "LineString", coordinates: allCoords };
}

interface PopupStation {
  station_id: string;
  name: string;
  lat: number;
  lon: number;
  bikes: number;
  capacity: number;
  fill: number;
  risk: string;
}

function findStopForStation(
  stationId: string,
  routes: Route[],
): { vanId: number; action: string; quantity: number } | null {
  for (const route of routes) {
    for (const stop of route.stops) {
      if (stop.station_id === stationId) {
        return { vanId: route.van_id, action: stop.action, quantity: stop.quantity };
      }
    }
  }
  return null;
}

interface MapViewProps {
  stations: Station[];
  counts: { starving: number; healthy: number; saturated: number };
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  routes?: Route[];
  theme: ThemeMode;
  systemKey: string;
}

const EMPTY_ROUTES: Route[] = [];

export default function MapView({
  stations,
  counts,
  loading,
  error,
  onRetry,
  routes,
  theme,
  systemKey,
}: MapViewProps) {
  const stableRoutes = routes ?? EMPTY_ROUTES;
  const mapRef = useRef<MapRef>(null);
  const [filter, setFilter] = useState<StationFilter>("all");
  const [routeGeometries, setRouteGeometries] = useState<
    Array<{ vanId: number; geometry: LineString }>
  >([]);
  const [popup, setPopup] = useState<PopupStation | null>(null);
  const stationsReadyForSystem = useRef<string | null>(null);
  const staleStationsRef = useRef<Station[]>(stations);

  useEffect(() => {
    stationsReadyForSystem.current = null;
    staleStationsRef.current = stations;
    setPopup(null);
    setFilter("all");
    setRouteGeometries([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [systemKey]);

  useEffect(() => {
    if (stations.length === 0 || !mapRef.current) return;
    if (stationsReadyForSystem.current === systemKey) return;
    if (stations === staleStationsRef.current) return;
    stationsReadyForSystem.current = systemKey;
    const lons = stations.map((s) => s.lon);
    const lats = stations.map((s) => s.lat);
    const centerLon = (Math.min(...lons) + Math.max(...lons)) / 2;
    const centerLat = (Math.min(...lats) + Math.max(...lats)) / 2;
    mapRef.current.flyTo({ center: [centerLon, centerLat], zoom: 12, duration: 1500 });
  }, [systemKey, stations]);

  useEffect(() => {
    if (stableRoutes.length === 0) {
      setRouteGeometries([]);
      return;
    }
    let cancelled = false;
    async function load() {
      const results: Array<{ vanId: number; geometry: LineString }> = [];
      for (const route of stableRoutes) {
        const geo = await fetchRouteGeometry(route.stops);
        if (cancelled) return;
        if (geo) results.push({ vanId: route.van_id, geometry: geo });
      }
      setRouteGeometries(results);
    }
    load();
    return () => { cancelled = true; };
  }, [stableRoutes]);

  const filtered = useMemo(() => {
    if (filter === "all") return stations;
    return stations.filter((s) => s.risk === filter);
  }, [stations, filter]);

  const geojson = useMemo(() => stationsToGeoJson(filtered), [filtered]);

  const routeLinesGeoJson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: routeGeometries.map((rg) => ({
        type: "Feature" as const,
        geometry: rg.geometry,
        properties: { van_id: rg.vanId },
      })),
    }),
    [routeGeometries],
  );

  const straightLinesGeoJson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: stableRoutes
        .filter((r) => r.stops.length >= 2 && !routeGeometries.some((rg) => rg.vanId === r.van_id))
        .map((route) => ({
          type: "Feature" as const,
          geometry: {
            type: "LineString" as const,
            coordinates: route.stops.map((s) => [s.lon, s.lat]),
          },
          properties: { van_id: route.van_id },
        })),
    }),
    [stableRoutes, routeGeometries],
  );

  const stopMarkersGeoJson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: stableRoutes.flatMap((route) =>
        route.stops.map((stop) => ({
          type: "Feature" as const,
          geometry: {
            type: "Point" as const,
            coordinates: [stop.lon, stop.lat],
          },
          properties: {
            action: stop.action,
            quantity: stop.quantity,
            name: stop.name,
            van_id: route.van_id,
          },
        })),
      ),
    }),
    [stableRoutes],
  );

  const handleMapClick = useCallback(
    (e: mapboxgl.MapLayerMouseEvent) => {
      const feature = e.features?.[0];
      if (!feature || feature.layer?.id !== "station-circles") {
        setPopup(null);
        return;
      }
      const props = feature.properties;
      if (!props) return;
      setPopup({
        station_id: props.station_id,
        name: props.name,
        lat: e.lngLat.lat,
        lon: e.lngLat.lng,
        bikes: props.bikes,
        capacity: props.capacity,
        fill: typeof props.fill === "string" ? parseFloat(props.fill) : props.fill,
        risk: props.risk,
      });
    },
    [],
  );

  if (!MAPBOX_TOKEN) {
    return (
      <div
        className="glass rounded-xl flex items-center justify-center"
        style={{ height: "100%", color: "var(--text3)" }}
      >
        <span style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
          Set NEXT_PUBLIC_MAPBOX_TOKEN in web/.env.local
        </span>
      </div>
    );
  }

  const riskColor = (risk: string) =>
    risk === "starving" ? "#ef4444" : risk === "saturated" ? "#f59e0b" : "#22c55e";

  const riskLabel = (risk: string) =>
    risk === "starving" ? "Starving" : risk === "saturated" ? "Saturated" : "Healthy";

  const initialCenter = stations.length > 0
    ? {
        longitude: stations.reduce((s, st) => s + st.lon, 0) / stations.length,
        latitude: stations.reduce((s, st) => s + st.lat, 0) / stations.length,
      }
    : { longitude: -73.98, latitude: 40.74 };

  return (
    <div className="relative rounded-xl overflow-hidden" style={{ height: "100%" }}>
      <ReactMapGL
        key={MAP_STYLES[theme]}
        ref={mapRef}
        initialViewState={{ ...initialCenter, zoom: 12 }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={MAP_STYLES[theme]}
        mapboxAccessToken={MAPBOX_TOKEN}
        attributionControl={false}
        interactiveLayerIds={["station-circles"]}
        onClick={handleMapClick}
        cursor="pointer"
      >
        <Source id="stations" type="geojson" data={geojson}>
          <Layer
            id="station-circles"
            type="circle"
            paint={{
              "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 3, 13, 5, 16, 8],
              "circle-color": [
                "match", ["get", "risk"],
                "starving", "#ef4444",
                "saturated", "#f59e0b",
                "healthy", "#22c55e",
                "#60a5fa",
              ],
              "circle-opacity": 0.85,
              "circle-stroke-width": 1,
              "circle-stroke-color": "rgba(0,0,0,0.3)",
            }}
          />
        </Source>

        {routeGeometries.length > 0 && (
          <Source id="route-lines" type="geojson" data={routeLinesGeoJson}>
            <Layer
              id="route-line-layer"
              type="line"
              paint={{
                "line-color": [
                  "match", ["get", "van_id"],
                  0, VAN_COLORS[0], 1, VAN_COLORS[1], 2, VAN_COLORS[2],
                  3, VAN_COLORS[3], 4, VAN_COLORS[4], 5, VAN_COLORS[5],
                  6, VAN_COLORS[6], 7, VAN_COLORS[7], 8, VAN_COLORS[8],
                  VAN_COLORS[9],
                ],
                "line-width": 4,
                "line-opacity": 0.9,
              }}
              layout={{ "line-cap": "round", "line-join": "round" }}
            />
          </Source>
        )}

        {straightLinesGeoJson.features.length > 0 && (
          <Source id="straight-lines" type="geojson" data={straightLinesGeoJson}>
            <Layer
              id="straight-line-layer"
              type="line"
              paint={{
                "line-color": [
                  "match", ["get", "van_id"],
                  0, VAN_COLORS[0], 1, VAN_COLORS[1], 2, VAN_COLORS[2],
                  3, VAN_COLORS[3], 4, VAN_COLORS[4], 5, VAN_COLORS[5],
                  6, VAN_COLORS[6], 7, VAN_COLORS[7], 8, VAN_COLORS[8],
                  VAN_COLORS[9],
                ],
                "line-width": 3,
                "line-dasharray": [2, 2],
                "line-opacity": 0.6,
              }}
            />
          </Source>
        )}

        {stableRoutes.length > 0 && (
          <Source id="stop-markers" type="geojson" data={stopMarkersGeoJson}>
            <Layer
              id="stop-marker-layer"
              type="circle"
              paint={{
                "circle-radius": 8,
                "circle-color": "white",
                "circle-stroke-width": 3,
                "circle-stroke-color": [
                  "match", ["get", "van_id"],
                  0, VAN_COLORS[0], 1, VAN_COLORS[1], 2, VAN_COLORS[2],
                  3, VAN_COLORS[3], 4, VAN_COLORS[4], 5, VAN_COLORS[5],
                  6, VAN_COLORS[6], 7, VAN_COLORS[7], 8, VAN_COLORS[8],
                  VAN_COLORS[9],
                ],
                "circle-opacity": 0.95,
              }}
            />
          </Source>
        )}

        {popup && (
          <Popup
            longitude={popup.lon}
            latitude={popup.lat}
            anchor="bottom"
            onClose={() => setPopup(null)}
            closeButton={true}
            closeOnClick={false}
            style={{ zIndex: 50 }}
          >
            <div style={{ padding: "4px 2px", minWidth: 180, color: "#0f172a", fontSize: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>{popup.name}</div>
              <div style={{ marginBottom: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                  <span style={{ color: "#475569", fontSize: 11 }}>Fill level</span>
                  <span style={{ fontWeight: 600 }}>{Math.round(popup.fill * 100)}%</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: "#e2e8f0", overflow: "hidden" }}>
                  <div
                    style={{
                      height: "100%",
                      width: `${Math.round(popup.fill * 100)}%`,
                      borderRadius: 3,
                      background: riskColor(popup.risk),
                      transition: "width 0.3s",
                    }}
                  />
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ color: "#475569" }}>{popup.bikes} / {popup.capacity} bikes</span>
                <span
                  style={{
                    fontWeight: 600, fontSize: 11, padding: "1px 8px", borderRadius: 10,
                    background: riskColor(popup.risk) + "22", color: riskColor(popup.risk),
                  }}
                >
                  {riskLabel(popup.risk)}
                </span>
              </div>
              {stableRoutes.length > 0 && (() => {
                const stopInfo = findStopForStation(popup.station_id, stableRoutes);
                if (!stopInfo) return null;
                const actionColor = stopInfo.action === "pickup" ? "#ef4444" : "#22c55e";
                const actionLabel = stopInfo.action === "pickup" ? "pick up" : "drop off";
                return (
                  <div
                    style={{
                      marginTop: 2, padding: "4px 8px", borderRadius: 6,
                      background: actionColor + "15", border: `1px solid ${actionColor}40`,
                      fontSize: 11, color: "#334155",
                    }}
                  >
                    <span style={{ fontWeight: 600, color: actionColor }}>Van {stopInfo.vanId + 1}</span>
                    {" stop — "}{actionLabel} {stopInfo.quantity} bikes
                  </div>
                );
              })()}
            </div>
          </Popup>
        )}
      </ReactMapGL>

      {/* Filter buttons */}
      <div className="absolute top-3 left-3 flex items-center gap-1.5" style={{ zIndex: 10 }}>
        {FILTER_BUTTONS.map(({ value, label }) => {
          const count = value === "all" ? stations.length : counts[value as keyof typeof counts];
          return (
            <button
              key={value}
              onClick={() => setFilter(value)}
              className="glass2 rounded-full px-3 py-1 transition-all"
              style={{
                fontSize: 11, fontWeight: 500, fontFamily: "var(--font-mono)",
                color: filter === value ? "var(--text)" : "var(--text3)",
                background: filter === value ? "var(--border2)" : "var(--glass2)",
                border: filter === value ? "1px solid var(--blue)" : "1px solid var(--border)",
              }}
            >
              {label} ({count})
            </button>
          );
        })}
      </div>

      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.4)", zIndex: 20 }}>
          <span style={{ color: "var(--text2)", fontFamily: "var(--font-mono)", fontSize: 13 }}>
            Loading stations...
          </span>
        </div>
      )}

      {/* Error overlay with retry */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center" style={{ background: "rgba(0,0,0,0.5)", zIndex: 20 }}>
          <div className="glass rounded-xl p-6" style={{ maxWidth: 360, textAlign: "center" }}>
            <div style={{ fontSize: 13, color: "var(--red)", marginBottom: 12 }}>{error}</div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="gradient-btn flex items-center gap-2 rounded-lg px-4 py-2"
                style={{ fontSize: 12, margin: "0 auto" }}
              >
                <RefreshCw size={14} />
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="absolute bottom-3 right-3 glass2 rounded-lg px-3 py-2 flex flex-col gap-1.5" style={{ zIndex: 10, fontSize: 11 }}>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5">
            <span className="inline-block rounded-full" style={{ width: 8, height: 8, background: "#ef4444" }} />
            <span style={{ color: "var(--text2)" }}>Starving</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block rounded-full" style={{ width: 8, height: 8, background: "#22c55e" }} />
            <span style={{ color: "var(--text2)" }}>Healthy</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block rounded-full" style={{ width: 8, height: 8, background: "#f59e0b" }} />
            <span style={{ color: "var(--text2)" }}>Saturated</span>
          </span>
        </div>
        {stableRoutes.length > 0 && (
          <div className="flex items-center gap-3" style={{ borderTop: "1px solid var(--border)", paddingTop: 4 }}>
            {stableRoutes.map((route, i) => (
              <span key={route.van_id} className="flex items-center gap-1.5">
                <span style={{ width: 16, height: 3, borderRadius: 2, background: VAN_COLORS[i % VAN_COLORS.length], display: "inline-block" }} />
                <span style={{ color: "var(--text2)" }}>Van {route.van_id + 1}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
