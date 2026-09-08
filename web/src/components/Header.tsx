"use client";

import { useState } from "react";
import { Bike, Info, Play, Sun, Moon, Sparkles } from "lucide-react";
import type { ThemeMode, TickPhase } from "@/lib/types";
import type { ValidatedSystem } from "@/lib/validateSystems";
import type { RegionFilter } from "@/hooks/useSystem";
import SystemSelector from "./SystemSelector";

interface HeaderProps {
  theme: ThemeMode;
  onThemeChange: (mode: ThemeMode) => void;
  onRunTick: () => void;
  phase: TickPhase;
  systems: ValidatedSystem[];
  selectedSystem: ValidatedSystem;
  onSystemChange: (system: ValidatedSystem) => void;
  systemsLoading?: boolean;
  forecastMethod?: "xgboost" | "persistence_baseline";
  regionFilter: RegionFilter;
  onRegionChange: (region: RegionFilter) => void;
  validationProgress: number;
  validationTotal: number;
  showAllTypes: boolean;
  onShowAllTypesChange: (show: boolean) => void;
}

function ForecastBadge({ systemId, forecastMethod }: { systemId: string; forecastMethod?: string }) {
  const [showTooltip, setShowTooltip] = useState(false);
  const isML = (systemId === "citi-bike-nyc" || systemId === "citi_bike_nyc") && forecastMethod === "xgboost";

  return (
    <div style={{ position: "relative", display: "inline-flex" }}>
      <div
        className="flex items-center gap-1.5 rounded-full px-2.5 py-0.5"
        style={{
          fontSize: 10,
          fontWeight: 600,
          fontFamily: "var(--font-mono)",
          background: isML ? "var(--green-d)" : "var(--amber-d)",
          color: isML ? "var(--green)" : "var(--amber)",
          border: `1px solid ${isML ? "var(--green)" : "var(--amber)"}33`,
          letterSpacing: "0.02em",
        }}
      >
        <span
          className="inline-block rounded-full"
          style={{ width: 5, height: 5, background: isML ? "var(--green)" : "var(--amber)" }}
        />
        {isML ? "ML model active" : "Baseline forecast"}
        {!isML && (
          <button
            onMouseEnter={() => setShowTooltip(true)}
            onMouseLeave={() => setShowTooltip(false)}
            onClick={() => setShowTooltip(!showTooltip)}
            style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex" }}
          >
            <Info size={10} style={{ color: "var(--amber)", opacity: 0.8 }} />
          </button>
        )}
      </div>
      {showTooltip && !isML && (
        <div
          className="glass"
          style={{
            position: "absolute",
            top: "calc(100% + 6px)",
            left: "50%",
            transform: "translateX(-50%)",
            width: 260,
            padding: "10px 12px",
            borderRadius: 10,
            fontSize: 11,
            lineHeight: 1.5,
            color: "var(--text2)",
            zIndex: 200,
            pointerEvents: "none",
          }}
        >
          XGBoost demand forecasting is currently trained on Citi Bike NYC data.
          Routing, planning, and approval work fully for all cities. Full ML
          coverage for this city is coming.
        </div>
      )}
    </div>
  );
}

const THEME_OPTIONS: { mode: ThemeMode; icon: React.ReactNode; label: string }[] = [
  { mode: "light", icon: <Sun size={14} />, label: "Light" },
  { mode: "dark", icon: <Moon size={14} />, label: "Dark" },
  { mode: "system", icon: <Sparkles size={14} />, label: "System" },
];

export default function Header({
  theme,
  onThemeChange,
  onRunTick,
  phase,
  systems,
  selectedSystem,
  onSystemChange,
  systemsLoading,
  forecastMethod,
  regionFilter,
  onRegionChange,
  validationProgress,
  validationTotal,
  showAllTypes,
  onShowAllTypesChange,
}: HeaderProps) {
  const isRunning = phase === "running";

  return (
    <header
      className="glass sticky top-0 z-50 flex items-center justify-between px-5"
      style={{ height: 52, borderRadius: 0, borderTop: "none", borderLeft: "none", borderRight: "none" }}
    >
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div
            className="flex items-center justify-center rounded-lg"
            style={{ width: 32, height: 32, background: "var(--grad-btn)" }}
          >
            <Bike size={18} color="white" />
          </div>
          <span
            className="font-semibold tracking-tight"
            style={{ color: "var(--text)", fontSize: 16 }}
          >
            Fleet Rebalancer
          </span>
        </div>

        <SystemSelector
          systems={systems}
          selected={selectedSystem}
          onSelect={onSystemChange}
          loading={systemsLoading}
          regionFilter={regionFilter}
          onRegionChange={onRegionChange}
          validationProgress={validationProgress}
          validationTotal={validationTotal}
          showAllTypes={showAllTypes}
          onShowAllTypesChange={onShowAllTypesChange}
        />

        <ForecastBadge systemId={selectedSystem.systemId} forecastMethod={forecastMethod} />
      </div>

      <div className="flex items-center gap-3">
        <div className="glass2 flex items-center rounded-full p-0.5" style={{ gap: 2 }}>
          {THEME_OPTIONS.map(({ mode, icon, label }) => (
            <button
              key={mode}
              onClick={() => onThemeChange(mode)}
              className="flex items-center gap-1.5 rounded-full px-3 py-1 transition-all"
              style={{
                fontSize: 12, fontWeight: 500,
                color: theme === mode ? "var(--text)" : "var(--text3)",
                background: theme === mode ? "var(--border2)" : "transparent",
              }}
            >
              {icon}
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>

        <button
          onClick={onRunTick}
          disabled={isRunning}
          className="gradient-btn flex items-center gap-2 rounded-lg px-4 py-2"
          style={{ fontSize: 13 }}
        >
          <Play size={14} fill="white" />
          <span>{isRunning ? "Analyzing..." : "Run Analysis"}</span>
        </button>
      </div>
    </header>
  );
}
