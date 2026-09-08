import type { GbfsSystem } from "./types";

export type SystemTier = 1 | 2 | 3;
export type SystemType = "docked" | "free_floating" | "mixed";

export interface ValidatedSystem extends GbfsSystem {
  tier: SystemTier;
  systemType: SystemType;
  stationCount?: number;
  tierReason?: string;
}

interface ValidationResult {
  tier: SystemTier;
  systemType: SystemType;
  stationCount?: number;
  reason?: string;
}

async function validateOne(
  system: GbfsSystem,
  timeoutMs = 3000,
): Promise<ValidationResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const discRes = await fetch(system.autoDiscoveryUrl, { signal: controller.signal });
    if (!discRes.ok) return { tier: 3, systemType: "docked", reason: `Discovery HTTP ${discRes.status}` };

    const discBody = await discRes.json();
    const data = discBody.data ?? {};

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

    const hasInfo = feeds.some((f) => f.name === "station_information");
    const hasStatus = feeds.some((f) => f.name === "station_status");
    if (!hasInfo || !hasStatus) {
      return { tier: 3, systemType: "free_floating", reason: "Missing station feeds" };
    }

    const statusFeed = feeds.find((f) => f.name === "station_status")!;
    const infoFeed = feeds.find((f) => f.name === "station_information")!;

    const [statusRes, infoRes] = await Promise.all([
      fetch(statusFeed.url, { signal: controller.signal }),
      fetch(infoFeed.url, { signal: controller.signal }),
    ]);

    if (!statusRes.ok || !infoRes.ok) {
      return { tier: 3, systemType: "docked", reason: "Feed fetch failed" };
    }

    const statusData = await statusRes.json();
    const infoData = await infoRes.json();

    const stations = infoData.data?.stations ?? [];
    const validStations = stations.filter(
      (s: any) => s.lat != null && s.lon != null && typeof s.lat === "number" && typeof s.lon === "number",
    );

    if (validStations.length < 10) {
      return { tier: 3, systemType: "docked", stationCount: validStations.length, reason: `Only ${validStations.length} stations` };
    }

    const withCapacity = validStations.filter((s: any) => s.capacity != null && s.capacity > 0);
    const capRatio = withCapacity.length / validStations.length;
    let systemType: SystemType;
    if (capRatio >= 0.8) systemType = "docked";
    else if (capRatio <= 0.2) systemType = "free_floating";
    else systemType = "mixed";

    const tsRaw = statusData.last_updated ?? statusData.data?.last_updated;
    if (tsRaw) {
      const ts = typeof tsRaw === "number" && tsRaw < 2e10 ? tsRaw * 1000 : tsRaw;
      const age = Date.now() - new Date(ts).getTime();
      const hoursOld = age / (1000 * 60 * 60);
      if (hoursOld > 48) {
        return { tier: 2, systemType, stationCount: validStations.length, reason: `Data ${Math.round(hoursOld)}h old` };
      }
    }

    return { tier: 1, systemType, stationCount: validStations.length };
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      return { tier: 3, systemType: "docked", reason: "Timeout" };
    }
    return { tier: 3, systemType: "docked", reason: (e as Error).message?.slice(0, 60) || "Fetch failed" };
  } finally {
    clearTimeout(timer);
  }
}

export async function validateSystems(
  systems: GbfsSystem[],
  batchSize = 20,
  onProgress?: (validated: ValidatedSystem[]) => void,
): Promise<ValidatedSystem[]> {
  const results: ValidatedSystem[] = [];

  for (let i = 0; i < systems.length; i += batchSize) {
    const batch = systems.slice(i, i + batchSize);
    const batchResults = await Promise.all(
      batch.map(async (system) => {
        const result = await validateOne(system);
        return {
          ...system,
          tier: result.tier,
          systemType: result.systemType,
          stationCount: result.stationCount,
          tierReason: result.reason,
        } as ValidatedSystem;
      }),
    );
    results.push(...batchResults);
    onProgress?.(results);
  }

  return results;
}
