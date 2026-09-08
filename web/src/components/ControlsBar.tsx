"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ChevronUp, Clock, Info, Truck } from "lucide-react";
import type { TickConstraints } from "@/lib/api";

type AutoCadence = "off" | "1h" | "2h" | "4h";
const CADENCE_HOURS: Record<AutoCadence, number> = { off: 0, "1h": 1, "2h": 2, "4h": 4 };
const CADENCE_OPTIONS: AutoCadence[] = ["off", "1h", "2h", "4h"];
const STORAGE_KEY = "fleet-rebalancer-auto-cadence";

interface ControlsBarProps {
  constraints: TickConstraints;
  onConstraintsChange: (c: TickConstraints) => void;
  onAutoChange: (hours: number) => void;
}

function Stepper({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  const s = step ?? 1;
  return (
    <div className="flex items-center gap-1.5">
      <span
        style={{
          fontSize: 9,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          color: "var(--text3)",
          whiteSpace: "nowrap",
        }}
      >
        {label}
      </span>
      <div className="flex items-center glass2 rounded" style={{ height: 24 }}>
        <button
          onClick={() => onChange(Math.max(min, value - s))}
          disabled={value <= min}
          style={{
            width: 20,
            height: 24,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "none",
            border: "none",
            cursor: value <= min ? "default" : "pointer",
            color: value <= min ? "var(--text3)" : "var(--text2)",
            padding: 0,
          }}
        >
          <ChevronDown size={12} />
        </button>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 13,
            fontWeight: 600,
            color: "var(--text)",
            minWidth: 28,
            textAlign: "center",
          }}
        >
          {value}
        </span>
        <button
          onClick={() => onChange(Math.min(max, value + s))}
          disabled={value >= max}
          style={{
            width: 20,
            height: 24,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "none",
            border: "none",
            cursor: value >= max ? "default" : "pointer",
            color: value >= max ? "var(--text3)" : "var(--text2)",
            padding: 0,
          }}
        >
          <ChevronUp size={12} />
        </button>
      </div>
    </div>
  );
}

export default function ControlsBar({ constraints, onConstraintsChange, onAutoChange }: ControlsBarProps) {
  const [cadence, setCadence] = useState<AutoCadence>("off");
  const [showTip, setShowTip] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as AutoCadence | null;
      if (stored && CADENCE_OPTIONS.includes(stored)) {
        setCadence(stored);
        onAutoChange(CADENCE_HOURS[stored]);
      }
    } catch {}
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleCadence = useCallback(
    (c: AutoCadence) => {
      setCadence(c);
      try { localStorage.setItem(STORAGE_KEY, c); } catch {}
      onAutoChange(CADENCE_HOURS[c]);
    },
    [onAutoChange],
  );

  return (
    <div
      className="glass flex items-center justify-between px-5"
      style={{
        height: 32,
        borderRadius: 0,
        borderLeft: "none",
        borderRight: "none",
        borderTop: "none",
      }}
    >
      <div className="flex items-center gap-4">
        <Stepper
          label="🚐 Vans"
          value={constraints.van_count ?? 3}
          min={1}
          max={10}
          onChange={(v) => onConstraintsChange({ ...constraints, van_count: v })}
        />

        <div style={{ width: 1, height: 16, background: "var(--border)", flexShrink: 0 }} />

        <Stepper
          label="📦 Capacity"
          value={constraints.van_capacity ?? 25}
          min={5}
          max={50}
          step={5}
          onChange={(v) => onConstraintsChange({ ...constraints, van_capacity: v })}
        />

        <div style={{ width: 1, height: 16, background: "var(--border)", flexShrink: 0 }} />

        <Stepper
          label="⏱ Shift"
          value={constraints.shift_budget_min ?? 120}
          min={60}
          max={240}
          step={15}
          onChange={(v) => onConstraintsChange({ ...constraints, shift_budget_min: v })}
        />
      </div>

      <div className="flex items-center gap-2" style={{ position: "relative" }}>
        <Clock size={11} style={{ color: "var(--text3)" }} />
        <span style={{ fontSize: 9, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text3)" }}>
          Auto-analyse
        </span>
        <div className="flex items-center glass2 rounded-full" style={{ gap: 1, padding: "1px 2px" }}>
          {CADENCE_OPTIONS.map((opt) => (
            <button
              key={opt}
              onClick={() => handleCadence(opt)}
              className="rounded-full px-2 transition-all"
              style={{
                fontSize: 10,
                fontWeight: 500,
                fontFamily: "var(--font-mono)",
                height: 20,
                background: cadence === opt ? "var(--border2)" : "transparent",
                color: cadence === opt ? "var(--text)" : "var(--text3)",
                border: "none",
                cursor: "pointer",
                textTransform: "uppercase",
              }}
            >
              {opt}
            </button>
          ))}
        </div>
        <button
          onMouseEnter={() => setShowTip(true)}
          onMouseLeave={() => setShowTip(false)}
          style={{ background: "none", border: "none", cursor: "pointer", padding: 0, display: "flex" }}
        >
          <Info size={10} style={{ color: "var(--text3)" }} />
        </button>
        {showTip && (
          <div
            className="glass"
            style={{
              position: "absolute",
              top: "calc(100% + 6px)",
              right: 0,
              width: 240,
              padding: "8px 10px",
              borderRadius: 8,
              fontSize: 10,
              lineHeight: 1.5,
              color: "var(--text2)",
              zIndex: 200,
              pointerEvents: "none",
            }}
          >
            Auto-analysis uses 1 Groq call per triggered tick · GitHub Actions not required.
          </div>
        )}
      </div>
    </div>
  );
}
