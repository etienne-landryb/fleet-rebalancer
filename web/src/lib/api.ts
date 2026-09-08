import type { TickResponse } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ??
  (typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? ""
    : "http://localhost:8000");
const SESSION_STORAGE_KEY = "fleet-rebalancer-session-id";

function createSessionId(): string {
  const cryptoApi = window.crypto;
  if (typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }
  if (typeof cryptoApi.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    cryptoApi.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0"));
    return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`;
  }
  return `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function getSessionId(): string {
  if (typeof window === "undefined") return "operator-1";
  const existing = window.localStorage.getItem(SESSION_STORAGE_KEY);
  if (existing) return existing;
  const sessionId = createSessionId();
  window.localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
  return sessionId;
}

function sessionHeaders(): HeadersInit {
  return { "X-Session-ID": getSessionId() };
}

export interface TickConstraints {
  van_count?: number;
  van_capacity?: number;
  shift_budget_min?: number;
}

export async function runTick(
  systemId?: string,
  discoveryUrl?: string,
  constraints?: TickConstraints,
): Promise<TickResponse> {
  const res = await fetch(`${API_BASE}/api/tick`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...sessionHeaders() },
    body: JSON.stringify({
      system_id: systemId,
      discovery_url: discoveryUrl,
      ...constraints,
    }),
  });
  if (!res.ok) throw new Error(`Analysis failed: ${res.status}`);
  return res.json();
}

export async function approvePlan(): Promise<TickResponse> {
  const res = await fetch(`${API_BASE}/api/approve`, { method: "POST", headers: sessionHeaders() });
  if (!res.ok) throw new Error(`Approve failed: ${res.status}`);
  return res.json();
}

export async function rejectPlan(): Promise<TickResponse> {
  const res = await fetch(`${API_BASE}/api/reject`, { method: "POST", headers: sessionHeaders() });
  if (!res.ok) throw new Error(`Reject failed: ${res.status}`);
  return res.json();
}

export async function getStatus(): Promise<TickResponse> {
  const res = await fetch(`${API_BASE}/api/status`, { headers: sessionHeaders() });
  if (!res.ok) throw new Error(`Status failed: ${res.status}`);
  return res.json();
}

export interface PlanRecord {
  id: string;
  system_id: string;
  created_at: string;
  tick_time: string;
  approval: string;
  routes: any[];
  projected_impact: any;
  work_orders: string;
  decision_trace: string[];
}

export async function getPlans(limit: number = 10): Promise<PlanRecord[]> {
  const res = await fetch(`${API_BASE}/api/plans?limit=${limit}`);
  if (!res.ok) throw new Error(`Plans failed: ${res.status}`);
  const data = await res.json();
  return data.plans ?? [];
}
