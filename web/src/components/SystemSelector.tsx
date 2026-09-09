"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, ChevronDown, Search, Star, X } from "lucide-react";
import type { ValidatedSystem } from "@/lib/validateSystems";
import type { RegionFilter } from "@/hooks/useSystem";
import { getRegion } from "@/hooks/useSystem";

function Flag({ countryCode }: { countryCode: string }) {
  const normalized = countryCode.trim().toLowerCase();
  if (!/^[a-z]{2}$/.test(normalized)) return <span aria-hidden="true">🌍</span>;
  return (
    <img
      src={`https://flagcdn.com/w20/${normalized}.png`}
      alt={`${countryCode.toUpperCase()} flag`}
      width={20}
      height={14}
      style={{ display: "inline-block", width: 20, height: 14, objectFit: "cover", verticalAlign: "-2px" }}
    />
  );
}

const TIER_DOT: Record<number, { color: string; label: string }> = {
  1: { color: "var(--green)", label: "Verified" },
  2: { color: "var(--amber)", label: "May be stale" },
  3: { color: "var(--text3)", label: "Unavailable" },
};

const TYPE_BADGE: Record<string, { color: string; label: string; tooltip: string }> = {
  docked: { color: "var(--green)", label: "Docked", tooltip: "Fixed stations with docks — rebalancing supported" },
  free_floating: { color: "var(--text3)", label: "Free-floating", tooltip: "Free-floating systems use different rebalancing logic — not yet supported" },
  mixed: { color: "var(--amber)", label: "Mixed", tooltip: "Mix of docked and free-floating — partial support" },
};

const REGION_OPTIONS: { value: RegionFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "north_america", label: "Americas" },
  { value: "europe", label: "Europe" },
  { value: "asia", label: "Asia" },
  { value: "oceania", label: "Oceania" },
  { value: "africa", label: "Africa" },
];

interface SystemSelectorProps {
  systems: ValidatedSystem[];
  selected: ValidatedSystem;
  onSelect: (system: ValidatedSystem) => void;
  loading?: boolean;
  regionFilter: RegionFilter;
  onRegionChange: (region: RegionFilter) => void;
  validationProgress: number;
  validationTotal: number;
  showAllTypes: boolean;
  onShowAllTypesChange: (show: boolean) => void;
}

export default function SystemSelector({
  systems,
  selected,
  onSelect,
  loading,
  regionFilter,
  onRegionChange,
  validationProgress,
  validationTotal,
  showAllTypes,
  onShowAllTypesChange,
}: SystemSelectorProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  const filtered = useMemo(() => {
    let list = systems;

    if (!showAllTypes) {
      list = list.filter((s) => s.systemType === "docked" || s.systemType === "mixed");
    }

    if (regionFilter !== "all") {
      list = list.filter((s) => getRegion(s.countryCode) === regionFilter);
    }

    if (query) {
      const q = query.toLowerCase();
      list = list.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.location.toLowerCase().includes(q) ||
          s.countryCode.toLowerCase().includes(q) ||
          s.systemId.toLowerCase().includes(q),
      );
    }

    return list;
  }, [systems, query, regionFilter, showAllTypes]);

  const listRef = useRef<HTMLDivElement>(null);
  const [showBackToTop, setShowBackToTop] = useState(false);

  const handleListScroll = useCallback(() => {
    if (!listRef.current) return;
    setShowBackToTop(listRef.current.scrollTop > 240);
  }, []);

  const CITI_BIKE_ID = "citi_bike_nyc";
  const pinnedSystem = useMemo(
    () => filtered.find((s) => s.systemId === CITI_BIKE_ID) ?? null,
    [filtered],
  );
  const filteredWithoutPinned = useMemo(
    () => filtered.filter((s) => s.systemId !== CITI_BIKE_ID),
    [filtered],
  );
  const grouped = useMemo(() => {
    const groups: Record<string, ValidatedSystem[]> = {};
    for (const s of filteredWithoutPinned) {
      const cc = s.countryCode || "??";
      if (!groups[cc]) groups[cc] = [];
      groups[cc].push(s);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredWithoutPinned]);

  const renderSystemButton = useCallback(
    (system: ValidatedSystem, pinned: boolean) => {
      const isSelected = system.systemId === selected.systemId && system.autoDiscoveryUrl === selected.autoDiscoveryUrl;
      const dot = TIER_DOT[system.tier] ?? TIER_DOT[2];
      const typeBadge = TYPE_BADGE[system.systemType] ?? TYPE_BADGE.docked;
      const isUnsupported = system.systemType === "free_floating";
      const isDisabled = system.tier === 3 || isUnsupported;

      return (
        <button
          key={system.systemId}
          onClick={() => {
            if (isDisabled) return;
            onSelect(system);
            setOpen(false);
            setQuery("");
          }}
          title={isUnsupported ? typeBadge.tooltip : undefined}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            width: "100%",
            padding: "6px 14px",
            background: isSelected ? "var(--blue-d)" : "transparent",
            border: "none",
            cursor: isDisabled ? "not-allowed" : "pointer",
            textAlign: "left",
            fontSize: 12,
            transition: "background 0.15s",
            opacity: isDisabled ? 0.45 : 1,
          }}
          onMouseEnter={(e) => {
            if (!isSelected && !isDisabled) e.currentTarget.style.background = "var(--glass2)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = isSelected ? "var(--blue-d)" : "transparent";
          }}
        >
          <span
            className="inline-block rounded-full shrink-0"
            style={{ width: 6, height: 6, background: dot.color }}
            title={dot.label}
          />
          <span style={{ color: "var(--text)", fontWeight: isSelected || pinned ? 600 : 400, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {pinned && <Star size={10} className="inline mr-1" style={{ color: "var(--amber)", verticalAlign: "-1px" }} />}
            <span aria-hidden="true" style={{ marginRight: 6 }}><Flag countryCode={system.countryCode} /></span>
            {system.name}
          </span>
          {pinned && (
            <span
              className="rounded-full shrink-0"
              style={{ fontSize: 9, fontFamily: "var(--font-mono)", padding: "1px 6px", color: "var(--green)", border: "1px solid var(--green)33", background: "var(--green)11" }}
            >
              ML model
            </span>
          )}
          <span
            className="rounded-full shrink-0"
            style={{
              fontSize: 9,
              fontFamily: "var(--font-mono)",
              padding: "1px 6px",
              color: typeBadge.color,
              border: `1px solid ${typeBadge.color}33`,
              background: `${typeBadge.color}11`,
            }}
          >
            {typeBadge.label}
          </span>
          {system.stationCount != null && (
            <span style={{ color: "var(--text3)", fontSize: 10, fontFamily: "var(--font-mono)", flexShrink: 0 }}>
              {system.stationCount}
            </span>
          )}
          {isDisabled && (system.tierReason || isUnsupported) && (
            <span style={{ color: "var(--text3)", fontSize: 9, fontFamily: "var(--font-mono)", flexShrink: 0 }}>
              {isUnsupported ? "Not supported" : system.tierReason}
            </span>
          )}
        </button>
      );
    },
    [selected, onSelect],
  );

  const tierDot = TIER_DOT[selected.tier] ?? TIER_DOT[1];

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(!open)}
        className="glass2 flex items-center gap-2 rounded-full px-3 py-1"
        style={{ fontSize: 12, border: "1px solid var(--border)", cursor: "pointer", background: "var(--glass2)" }}
      >
        <span
          className="inline-block rounded-full"
          style={{ width: 6, height: 6, background: tierDot.color, boxShadow: `0 0 6px ${tierDot.color}` }}
        />
        <span style={{ color: "var(--text)", fontFamily: "var(--font-mono)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {loading ? "Loading..." : <><span aria-hidden="true"><Flag countryCode={selected.countryCode} /></span>{` ${selected.name}`}</>}
        </span>
        <span style={{ color: "var(--text3)", fontSize: 11 }}>
          {selected.location ? `· ${selected.location}` : ""}
        </span>
        <ChevronDown size={12} style={{ color: "var(--text3)" }} />
      </button>

      {open && (
        <div
          className="glass"
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            width: 420,
            maxHeight: 480,
            borderRadius: 12,
            zIndex: 100,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Region filter */}
          <div style={{ padding: "8px 10px 4px", display: "flex", gap: 4, flexWrap: "wrap" }}>
            {REGION_OPTIONS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => onRegionChange(value)}
                className="rounded-full px-2.5 py-0.5"
                style={{
                  fontSize: 10,
                  fontWeight: 500,
                  fontFamily: "var(--font-mono)",
                  color: regionFilter === value ? "var(--text)" : "var(--text3)",
                  background: regionFilter === value ? "var(--border2)" : "transparent",
                  border: regionFilter === value ? "1px solid var(--blue)" : "1px solid var(--border)",
                  cursor: "pointer",
                }}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div style={{ padding: "4px 10px 8px", borderBottom: "1px solid var(--border)" }}>
            <div className="flex items-center gap-2" style={{ background: "var(--bg2)", borderRadius: 8, padding: "6px 10px" }}>
              <Search size={14} style={{ color: "var(--text3)", flexShrink: 0 }} />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by city, country, or system..."
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  fontSize: 12,
                  color: "var(--text)",
                  fontFamily: "var(--font-sans)",
                }}
              />
              {query && (
                <button onClick={() => setQuery("")} style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}>
                  <X size={12} style={{ color: "var(--text3)" }} />
                </button>
              )}
            </div>
          </div>

          {/* Type filter + validation progress */}
          <div style={{ padding: "4px 14px 0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <label
              style={{ fontSize: 10, color: "var(--text3)", fontFamily: "var(--font-mono)", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
            >
              <input
                type="checkbox"
                checked={showAllTypes}
                onChange={(e) => onShowAllTypesChange(e.target.checked)}
                style={{ width: 12, height: 12, accentColor: "var(--blue)" }}
              />
              Show all system types
            </label>
            {validationTotal > 0 && validationProgress < validationTotal && (
              <span style={{ fontSize: 10, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>
                {validationProgress}/{validationTotal}
              </span>
            )}
          </div>

          {/* System list */}
          <div ref={listRef} onScroll={handleListScroll} style={{ flex: 1, overflowY: "auto", padding: "4px 0", position: "relative" }}>
            {grouped.length === 0 && !pinnedSystem && (
              <div style={{ padding: "16px", textAlign: "center", fontSize: 12, color: "var(--text3)" }}>
                No systems match your search
              </div>
            )}

            {/* Pinned: Citi Bike NYC */}
            {pinnedSystem && (
              <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: 4, marginBottom: 4 }}>
                {renderSystemButton(pinnedSystem, true)}
              </div>
            )}

            {grouped.map(([cc, items]) => (
              <div key={cc}>
                <div
                  style={{
                    padding: "6px 14px 4px",
                    fontSize: 10,
                    fontWeight: 600,
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    color: "var(--text3)",
                  }}
                >
                  <Flag countryCode={cc} /> {cc}
                </div>
                {items.map((system) => renderSystemButton(system, false))}
              </div>
            ))}

            {/* Back to top */}
            {showBackToTop && (
              <button
                onClick={() => listRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
                className="glass2 flex items-center gap-1 rounded-full px-3 py-1"
                style={{
                  position: "sticky", bottom: 8, left: "50%", transform: "translateX(-50%)",
                  fontSize: 10, fontWeight: 500, fontFamily: "var(--font-mono)",
                  color: "var(--blue)", border: "1px solid var(--blue)33",
                  cursor: "pointer", zIndex: 10,
                }}
              >
                <ArrowUp size={10} />Back to top
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
