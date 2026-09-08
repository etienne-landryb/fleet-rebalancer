"use client";

import { useCallback, useEffect, useState } from "react";
import type { Station } from "@/lib/types";

function classifyStation(
  bikesAvailable: number,
  docksAvailable: number,
  capacity: number,
): "starving" | "saturated" | "healthy" {
  if (capacity === 0) return "healthy";
  const fill = bikesAvailable / capacity;
  if (fill <= 0.15) return "starving";
  if (fill >= 0.85) return "saturated";
  return "healthy";
}

function extractName(raw: unknown): string {
  if (typeof raw === "string") return raw;
  if (Array.isArray(raw) && raw.length > 0) return raw[0].text ?? "";
  if (raw && typeof raw === "object" && "text" in raw) return (raw as { text: string }).text;
  return "";
}

function parseFeedUrls(body: any): { infoUrl: string; statusUrl: string } {
  const data = body.data ?? {};
  let feeds: Array<{ name: string; url: string }> = [];

  if (Array.isArray(data.feeds)) {
    feeds = data.feeds;
  } else {
    for (const val of Object.values(data)) {
      if (val && typeof val === "object" && "feeds" in (val as any)) {
        feeds = (val as any).feeds;
        break;
      }
    }
  }

  const infoFeed = feeds.find((f) => f.name === "station_information");
  const statusFeed = feeds.find((f) => f.name === "station_status");

  if (!infoFeed || !statusFeed) {
    const available = feeds.map((f) => f.name).join(", ");
    throw new Error(
      `This system doesn't provide station data. Available feeds: ${available || "none"}`,
    );
  }

  return { infoUrl: infoFeed.url, statusUrl: statusFeed.url };
}

export interface GbfsData {
  stations: Station[];
  counts: { starving: number; healthy: number; saturated: number };
  health: number | null;
  lastUpdated: Date | null;
  loading: boolean;
  error: string | null;
  retry: () => void;
}

export function useGbfs(discoveryUrl: string | null): GbfsData {
  const [stations, setStations] = useState<Station[]>([]);
  const [counts, setCounts] = useState({ starving: 0, healthy: 0, saturated: 0 });
  const [health, setHealth] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);

  useEffect(() => {
    if (!discoveryUrl) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    const signal = controller.signal;

    async function fetchData() {
      setLoading(true);
      setError(null);
      setStations([]);
      setCounts({ starving: 0, healthy: 0, saturated: 0 });
      setHealth(null);

      try {
        const discRes = await fetch(discoveryUrl!, { signal });
        if (!discRes.ok) throw new Error(`Discovery failed (${discRes.status})`);
        const discBody = await discRes.json();
        const { infoUrl, statusUrl } = parseFeedUrls(discBody);

        const [infoRes, statusRes] = await Promise.all([
          fetch(infoUrl, { signal }),
          fetch(statusUrl, { signal }),
        ]);
        if (!infoRes.ok) throw new Error(`Station info failed (${infoRes.status})`);
        if (!statusRes.ok) throw new Error(`Station status failed (${statusRes.status})`);

        const infoData = await infoRes.json();
        const statusData = await statusRes.json();

        const infoLookup: Record<string, { name: string; lat: number; lon: number; capacity: number }> = {};
        for (const s of infoData.data?.stations ?? []) {
          infoLookup[s.station_id] = {
            name: extractName(s.name),
            lat: s.lat,
            lon: s.lon,
            capacity: s.capacity ?? 0,
          };
        }

        const merged: Station[] = [];
        let starving = 0, healthy = 0, saturated = 0;

        for (const s of statusData.data?.stations ?? []) {
          const info = infoLookup[s.station_id];
          if (!info || !info.lat || !info.lon) continue;
          const bikes = s.num_bikes_available ?? 0;
          const docks = s.num_docks_available ?? 0;
          const capacity = info.capacity || bikes + docks;
          const fill = capacity > 0 ? bikes / capacity : 0.5;
          const risk = classifyStation(bikes, docks, capacity);

          if (risk === "starving") starving++;
          else if (risk === "saturated") saturated++;
          else healthy++;

          merged.push({
            station_id: s.station_id,
            name: info.name,
            lat: info.lat,
            lon: info.lon,
            capacity,
            num_bikes_available: bikes,
            num_docks_available: docks,
            fill_level: fill,
            risk,
          });
        }

        if (merged.length === 0) {
          throw new Error("No stations found — this system may not have docked stations.");
        }

        const total = merged.length;
        const healthVal = (total - starving - saturated) / total;

        const tsRaw = statusData.last_updated ?? statusData.data?.last_updated;
        const ts = tsRaw ? new Date(typeof tsRaw === "number" && tsRaw < 2e10 ? tsRaw * 1000 : tsRaw) : null;

        setStations(merged);
        setCounts({ starving, healthy, saturated });
        setHealth(healthVal);
        setLastUpdated(ts);
        setError(null);
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        setError(e instanceof Error ? e.message : "Failed to load station data");
        setStations([]);
        setCounts({ starving: 0, healthy: 0, saturated: 0 });
        setHealth(null);
      } finally {
        if (!signal.aborted) setLoading(false);
      }
    }

    fetchData();
    return () => controller.abort();
  }, [discoveryUrl, retryCount]);

  const retry = useCallback(() => setRetryCount((c) => c + 1), []);

  return { stations, counts, health, lastUpdated, loading, error, retry };
}
