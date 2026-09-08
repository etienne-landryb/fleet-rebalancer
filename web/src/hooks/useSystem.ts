"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { GbfsSystem } from "@/lib/types";
import type { ValidatedSystem } from "@/lib/validateSystems";
import { validateSystems } from "@/lib/validateSystems";

const SYSTEMS_CSV_URL =
  "https://raw.githubusercontent.com/MobilityData/gbfs/master/systems.csv";

const STORAGE_KEY = "fleet-rebalancer-system";

export type RegionFilter = "all" | "north_america" | "europe" | "asia" | "south_america" | "oceania" | "africa";

const REGION_COUNTRIES: Record<Exclude<RegionFilter, "all">, Set<string>> = {
  north_america: new Set(["US", "CA", "MX"]),
  europe: new Set([
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LT", "LU", "LV", "MT", "NL",
    "NO", "PL", "PT", "RO", "SE", "SI", "SK", "UA", "RS", "BA", "ME", "MK", "AL",
  ]),
  asia: new Set([
    "JP", "KR", "CN", "TW", "SG", "IN", "TH", "MY", "ID", "PH", "VN",
    "IL", "AE", "TR", "KZ", "UZ",
  ]),
  south_america: new Set(["BR", "AR", "CL", "CO", "PE", "EC", "UY", "PY", "VE"]),
  oceania: new Set(["AU", "NZ"]),
  africa: new Set(["ZA", "KE", "NG", "EG", "MA", "TN", "GH", "RW"]),
};

export function getRegion(countryCode: string): Exclude<RegionFilter, "all"> | null {
  for (const [region, countries] of Object.entries(REGION_COUNTRIES)) {
    if (countries.has(countryCode)) return region as Exclude<RegionFilter, "all">;
  }
  return null;
}

const CURATED_SYSTEMS: ValidatedSystem[] = [
  { systemId: "citi_bike_nyc", name: "Citi Bike", location: "New York, NY", countryCode: "US", autoDiscoveryUrl: "https://gbfs.citibikenyc.com/gbfs/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "divvy_chicago", name: "Divvy", location: "Chicago, IL", countryCode: "US", autoDiscoveryUrl: "https://gbfs.divvybikes.com/gbfs/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "capital_bikeshare", name: "Capital Bike Share", location: "Washington, DC", countryCode: "US", autoDiscoveryUrl: "https://gbfs.capitalbikeshare.com/gbfs/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "bay_wheels", name: "Bay Wheels", location: "San Francisco, CA", countryCode: "US", autoDiscoveryUrl: "https://gbfs.baywheels.com/gbfs/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "bluebikes", name: "Bluebikes", location: "Boston, MA", countryCode: "US", autoDiscoveryUrl: "https://gbfs.bluebikes.com/gbfs/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "bixi_montreal", name: "BIXI Montréal", location: "Montréal, QC", countryCode: "CA", autoDiscoveryUrl: "https://gbfs.velobixi.com/gbfs/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "bike_share_toronto", name: "Bike Share Toronto", location: "Toronto, ON", countryCode: "CA", autoDiscoveryUrl: "https://tor.publicbikesystem.net/ube/gbfs/v1/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "velib_paris", name: "Vélib' Métropole", location: "Paris", countryCode: "FR", autoDiscoveryUrl: "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "oslobysykkel", name: "Oslo Bysykkel", location: "Oslo", countryCode: "NO", autoDiscoveryUrl: "https://gbfs.urbansharing.com/oslobysykkel.no/gbfs.json", tier: 1, systemType: "docked" },
  { systemId: "nextbike_linz", name: "Linz city bike", location: "Linz", countryCode: "AT", autoDiscoveryUrl: "https://gbfs.nextbike.net/maps/gbfs/v2/nextbike_al/gbfs.json", tier: 1, systemType: "docked" },
];

const DEFAULT_SYSTEM = CURATED_SYSTEMS[0];

function urlHost(url: string): string {
  try { return new URL(url).hostname; } catch { return ""; }
}

const CURATED_HOSTS = new Set(CURATED_SYSTEMS.map((s) => urlHost(s.autoDiscoveryUrl)));
const CURATED_IDS = new Set(CURATED_SYSTEMS.map((s) => s.systemId));

function isCurated(s: { systemId: string; autoDiscoveryUrl: string }): boolean {
  return CURATED_IDS.has(s.systemId) || CURATED_HOSTS.has(urlHost(s.autoDiscoveryUrl));
}

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (const ch of line) {
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === "," && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current.trim());
  return result;
}

function parseSystemsCSV(text: string): GbfsSystem[] {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];

  const headers = parseCSVLine(lines[0]).map((h) => h.toLowerCase().replace(/\s+/g, "_"));
  const countryIdx = headers.indexOf("country_code");
  const nameIdx = headers.indexOf("name");
  const locationIdx = headers.indexOf("location");
  const systemIdIdx = headers.indexOf("system_id");
  const discoveryIdx = headers.indexOf("auto-discovery_url");

  const systems: GbfsSystem[] = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = parseCSVLine(lines[i]);
    const discoveryUrl = vals[discoveryIdx] ?? "";
    if (!discoveryUrl || !discoveryUrl.startsWith("http")) continue;

    systems.push({
      systemId: vals[systemIdIdx] ?? "",
      name: vals[nameIdx] ?? "",
      location: vals[locationIdx] ?? "",
      countryCode: vals[countryIdx] ?? "",
      autoDiscoveryUrl: discoveryUrl,
    });
  }

  const seen = new Set<string>();
  const deduped = systems.filter((s) => {
    if (seen.has(s.systemId)) return false;
    seen.add(s.systemId);
    return true;
  });

  deduped.sort((a, b) => {
    const cc = a.countryCode.localeCompare(b.countryCode);
    if (cc !== 0) return cc;
    return a.name.localeCompare(b.name);
  });

  return deduped;
}

export function useSystem() {
  const [systems, setSystems] = useState<ValidatedSystem[]>(CURATED_SYSTEMS);
  const [selected, setSelectedState] = useState<ValidatedSystem>(DEFAULT_SYSTEM);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [validationProgress, setValidationProgress] = useState<number>(0);
  const [validationTotal, setValidationTotal] = useState<number>(0);
  const [regionFilter, setRegionFilter] = useState<RegionFilter>("all");
  const [showAllTypes, setShowAllTypes] = useState(false);
  const abortRef = useRef(false);

  useEffect(() => {
    abortRef.current = false;

    async function load() {
      try {
        const res = await fetch(SYSTEMS_CSV_URL);
        if (!res.ok) throw new Error(`Failed to fetch systems catalog (${res.status})`);
        const text = await res.text();
        const parsed = parseSystemsCSV(text);
        if (parsed.length === 0) throw new Error("No systems found in catalog");

        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const match = parsed.find((s) => s.systemId === stored) ??
                        CURATED_SYSTEMS.find((s) => s.systemId === stored);
          if (match) {
            const validated: ValidatedSystem = "tier" in match && "systemType" in match
              ? match as ValidatedSystem
              : { ...match, tier: (match as any).tier ?? 2, systemType: (match as any).systemType ?? "docked" };
            setSelectedState(validated);
          }
        }

        setLoading(false);

        const nonCurated = parsed.filter((s) => !isCurated(s));
        setValidationTotal(nonCurated.length);

        const validated = await validateSystems(nonCurated, 20, (progress) => {
          if (abortRef.current) return;
          setValidationProgress(progress.length);
          const tier1and2 = progress.filter((s) => s.tier <= 2);
          if (tier1and2.length > 0) {
            setSystems((prev) => {
              const merged = [...CURATED_SYSTEMS];
              for (const s of tier1and2) {
                if (!isCurated(s)) merged.push(s);
              }
              merged.sort((a, b) => {
                if (a.tier !== b.tier) return a.tier - b.tier;
                const cc = a.countryCode.localeCompare(b.countryCode);
                if (cc !== 0) return cc;
                return a.name.localeCompare(b.name);
              });
              return merged;
            });
          }
        });

        if (abortRef.current) return;

        const tier1and2 = validated.filter((s) => s.tier <= 2);
        const merged = [...CURATED_SYSTEMS];
        for (const s of tier1and2) {
          if (!isCurated(s)) merged.push(s);
        }
        merged.sort((a, b) => {
          if (a.tier !== b.tier) return a.tier - b.tier;
          const cc = a.countryCode.localeCompare(b.countryCode);
          if (cc !== 0) return cc;
          return a.name.localeCompare(b.name);
        });
        setSystems(merged);
        setValidationProgress(nonCurated.length);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load systems");
        setLoading(false);
      }
    }
    load();
    return () => { abortRef.current = true; };
  }, []);

  const setSelected = useCallback(
    (system: ValidatedSystem) => {
      setSelectedState(system);
      localStorage.setItem(STORAGE_KEY, system.systemId);
    },
    [],
  );

  return {
    systems,
    selected,
    setSelected,
    loading,
    error,
    validationProgress,
    validationTotal,
    regionFilter,
    setRegionFilter,
    showAllTypes,
    setShowAllTypes,
  };
}
