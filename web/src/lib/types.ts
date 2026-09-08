export type TickPhase =
  | "idle"
  | "running"
  | "approval"
  | "dispatched"
  | "rejected";

export interface Station {
  station_id: string;
  name: string;
  lat: number;
  lon: number;
  capacity: number;
  num_bikes_available: number;
  num_docks_available: number;
  fill_level: number;
  risk: "starving" | "saturated" | "healthy";
}

export interface Stop {
  station_id: string;
  name: string;
  lat: number;
  lon: number;
  action: "pickup" | "dropoff";
  quantity: number;
}

export interface Route {
  van_id: number;
  stops: Stop[];
  total_pickups: number;
  total_dropoffs: number;
  distance_km: number;
  duration_min: number;
}

export interface Plan {
  routes: Route[];
  feasible: boolean;
}

export interface ImpactResult {
  do_nothing_health: number;
  planned_health: number;
  health_improvement: number;
  do_nothing_starving: number;
  planned_starving: number;
  do_nothing_saturated: number;
  planned_saturated: number;
  bikes_moved: number;
}

export interface KpiData {
  health: number;
  starving: number;
  saturated: number;
}

export interface TickState {
  phase: TickPhase;
  trigger: boolean;
  stations: Station[];
  plan: Plan | null;
  projectedImpact: ImpactResult | null;
  workOrders: string;
  decisionTrace: string[];
  llmCalls: number;
  replans: number;
  kpi: KpiData | null;
}

export type ThemeMode = "dark" | "light" | "system";

export interface GbfsSystem {
  systemId: string;
  name: string;
  location: string;
  countryCode: string;
  autoDiscoveryUrl: string;
}

export interface TickResponse {
  phase: string;
  trigger: boolean;
  stations_count: number;
  decision_trace: string[];
  node_details: Record<string, string>;
  plan: Route[];
  projected_impact: ImpactResult | null;
  work_orders: string;
  llm_calls: number;
  replan_count: number;
  kpi: KpiData;
  forecast_method: "xgboost" | "persistence_baseline";
  error: string | null;
  idle_reason: string | null;
}
