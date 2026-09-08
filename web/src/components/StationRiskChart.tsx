"use client";

import type { Station } from "@/lib/types";

interface StationRiskChartProps {
  stations: Station[];
  embedded?: boolean;
}

function riskColor(risk: string): string {
  if (risk === "starving") return "var(--red)";
  if (risk === "saturated") return "var(--amber)";
  return "var(--green)";
}

function riskBg(risk: string): string {
  if (risk === "starving") return "var(--red-d)";
  if (risk === "saturated") return "var(--amber-d)";
  return "var(--green-d)";
}

export default function StationRiskChart({ stations, embedded }: StationRiskChartProps) {
  if (stations.length === 0) {
    return (
      <div className={embedded ? "px-4 flex items-center justify-center" : "glass rounded-xl p-4 flex items-center justify-center"} style={{ height: "100%" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 12, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>
            Waiting for station data...
          </div>
        </div>
      </div>
    );
  }

  const atRisk = stations
    .filter((s) => s.risk !== "healthy")
    .sort((a, b) => a.fill_level - b.fill_level)
    .slice(0, 15);

  if (atRisk.length === 0) {
    return (
      <div className={embedded ? "px-4 flex items-center justify-center" : "glass rounded-xl p-4 flex items-center justify-center"} style={{ height: "100%" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--green)", marginBottom: 4 }}>
            All Clear
          </div>
          <div style={{ fontSize: 12, color: "var(--text3)" }}>
            No stations at risk
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={embedded ? "px-4 flex flex-col" : "glass rounded-xl p-4 flex flex-col"} style={{ height: "100%" }}>
      {!embedded && (
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text2)",
            marginBottom: 8,
            flexShrink: 0,
          }}
        >
          At-Risk Stations
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 3 }}>
        {atRisk.map((s) => {
          const pct = Math.round(s.fill_level * 100);
          return (
            <div key={s.station_id} className="flex items-center gap-2" style={{ minHeight: 22 }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: riskColor(s.risk),
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  color: "var(--text2)",
                  width: 100,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
                title={s.name}
              >
                {s.name}
              </span>
              <div
                style={{
                  flex: 1,
                  height: 10,
                  borderRadius: 5,
                  background: "var(--bg2)",
                  overflow: "hidden",
                  position: "relative",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: `${pct}%`,
                    borderRadius: 5,
                    background: riskColor(s.risk),
                    opacity: 0.7,
                    transition: "width 0.3s",
                  }}
                />
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontFamily: "var(--font-mono)",
                  color: riskColor(s.risk),
                  width: 32,
                  textAlign: "right",
                  flexShrink: 0,
                }}
              >
                {pct}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
