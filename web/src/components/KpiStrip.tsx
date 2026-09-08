"use client";

import { Clock, AlertTriangle } from "lucide-react";

interface KpiStripProps {
  health: number | null;
  starving: number | null;
  saturated: number | null;
  totalStations?: number;
  lastUpdated?: Date | null;
}

function Freshness({ lastUpdated }: { lastUpdated: Date | null }) {
  if (!lastUpdated) return null;
  const now = new Date();
  const diffMs = now.getTime() - lastUpdated.getTime();
  const diffMin = Math.round(diffMs / 60000);
  const timeStr = lastUpdated.toLocaleTimeString("en-US", {
    hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC",
  });
  let color = "var(--text3)";
  let icon = null;
  if (diffMin > 30) { color = "var(--red)"; icon = <AlertTriangle size={9} style={{ color }} />; }
  else if (diffMin > 10) { color = "var(--amber)"; icon = <AlertTriangle size={9} style={{ color }} />; }
  return (
    <div className="flex items-center gap-1" style={{ fontSize: 9, color, fontFamily: "var(--font-mono)", whiteSpace: "nowrap" }}>
      <Clock size={9} />{icon}
      <span>Data as of {timeStr} UTC · {diffMin < 1 ? "<1" : diffMin} min ago</span>
    </div>
  );
}

export default function KpiStrip({ health, starving, saturated, totalStations, lastUpdated }: KpiStripProps) {
  const stationsLabel = totalStations != null ? `of ${totalStations.toLocaleString()}` : "";

  return (
    <div
      className="glass2 flex items-center rounded-lg"
      style={{ height: 48, padding: "0 16px", gap: 0 }}
    >
      {/* Health */}
      <div className="flex flex-col justify-center" style={{ minWidth: 100 }}>
        <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text3)", lineHeight: 1 }}>
          Network Health
        </div>
        <div className="flex items-baseline gap-1.5">
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 24, fontWeight: 700, color: "var(--green)", lineHeight: 1.1 }}>
            {health != null ? `${Math.round(health * 100)}%` : "—"}
          </span>
          {stationsLabel && (
            <span style={{ fontSize: 9, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>{stationsLabel}</span>
          )}
        </div>
      </div>

      <div style={{ width: 1, height: 28, background: "var(--border)", margin: "0 16px", flexShrink: 0 }} />

      {/* Starving */}
      <div className="flex flex-col justify-center" style={{ minWidth: 80 }}>
        <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text3)", lineHeight: 1 }}>
          Starving
        </div>
        <div className="flex items-baseline gap-1.5">
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 24, fontWeight: 700, color: "var(--red)", lineHeight: 1.1 }}>
            {starving != null ? String(starving) : "—"}
          </span>
          <span style={{ fontSize: 9, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>stations</span>
        </div>
      </div>

      <div style={{ width: 1, height: 28, background: "var(--border)", margin: "0 16px", flexShrink: 0 }} />

      {/* Saturated */}
      <div className="flex flex-col justify-center" style={{ minWidth: 80 }}>
        <div style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text3)", lineHeight: 1 }}>
          Saturated
        </div>
        <div className="flex items-baseline gap-1.5">
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 24, fontWeight: 700, color: "var(--amber)", lineHeight: 1.1 }}>
            {saturated != null ? String(saturated) : "—"}
          </span>
          <span style={{ fontSize: 9, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>stations</span>
        </div>
      </div>

      {/* Spacer + Freshness */}
      <div style={{ flex: 1 }} />
      {lastUpdated !== undefined && <Freshness lastUpdated={lastUpdated ?? null} />}
    </div>
  );
}
