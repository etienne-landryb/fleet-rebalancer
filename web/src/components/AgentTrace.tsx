"use client";

import {
  AlertTriangle,
  MessageSquare,
  Navigation,
  Radio,
  Scale,
  Send,
  TrendingUp,
  UserCheck,
} from "lucide-react";
import type { TickPhase, TickResponse } from "@/lib/types";

const GRAPH_NODES = [
  { id: "ingest", label: "Ingest", Icon: Radio },
  { id: "forecast", label: "Forecast", Icon: TrendingUp },
  { id: "assess_imbalance", label: "Assess", Icon: AlertTriangle },
  { id: "plan", label: "Plan", Icon: Navigation },
  { id: "evaluate_plan", label: "Evaluate", Icon: Scale },
  { id: "explain", label: "Explain", Icon: MessageSquare },
  { id: "human_approval", label: "Approve", Icon: UserCheck },
  { id: "dispatch", label: "Dispatch", Icon: Send },
];

type NodeState = "pending" | "running" | "done" | "hold";

function getNodeState(
  nodeId: string,
  trace: string[],
  visibleNodes: number,
  phase: TickPhase,
): NodeState {
  const traceIdx = trace.indexOf(nodeId);

  if (traceIdx === -1) {
    if (phase === "running") {
      const graphIdx = GRAPH_NODES.findIndex((n) => n.id === nodeId);
      const lastVisible = visibleNodes > 0 ? trace[visibleNodes - 1] : undefined;
      const lastGraphIdx = lastVisible ? GRAPH_NODES.findIndex((n) => n.id === lastVisible) : -1;
      if (graphIdx === lastGraphIdx + 1) return "running";
    }
    return "pending";
  }

  if (traceIdx >= visibleNodes) return "pending";
  if (traceIdx === visibleNodes - 1 && phase === "running") return "running";
  if (nodeId === "human_approval" && phase === "approval") return "hold";
  return "done";
}

const STATE_STYLES: Record<NodeState, { bg: string; color: string; shadow: string }> = {
  pending: { bg: "transparent", color: "var(--text3)", shadow: "none" },
  running: { bg: "var(--blue)", color: "white", shadow: "0 0 12px var(--blue-d)" },
  done: { bg: "var(--green)", color: "white", shadow: "0 0 8px var(--green-d)" },
  hold: { bg: "var(--amber)", color: "white", shadow: "0 0 8px var(--amber-d)" },
};

interface AgentTraceProps {
  phase: TickPhase;
  response: TickResponse | null;
  visibleNodes: number;
  embedded?: boolean;
}

export default function AgentTrace({ phase, response, visibleNodes, embedded }: AgentTraceProps) {
  const trace = response?.decision_trace ?? [];
  const details = response?.node_details ?? {};

  return (
    <div className={embedded ? "px-3" : "glass rounded-xl p-3"} style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {!embedded && (
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--text2)",
            marginBottom: 6,
            flexShrink: 0,
          }}
        >
          Decision Trace
        </div>
      )}

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
        {GRAPH_NODES.map((node) => {
          const state = getNodeState(node.id, trace, visibleNodes, phase);
          const styles = STATE_STYLES[state];
          const detail = details[node.id] ?? "";

          return (
            <div key={node.id} className="flex items-center gap-2" style={{ height: 28, flexShrink: 0 }}>
              <div
                className="flex items-center justify-center rounded-md shrink-0 transition-all"
                style={{
                  width: 22,
                  height: 22,
                  background: styles.bg,
                  boxShadow: styles.shadow,
                  border: state === "pending" ? "1px solid var(--border2)" : "none",
                  animation: state === "running" ? "pulse 1.5s ease-in-out infinite" : undefined,
                }}
              >
                <node.Icon size={12} color={styles.color} />
              </div>

              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  fontWeight: 500,
                  color: state === "pending" ? "var(--text3)" : "var(--text)",
                  flexShrink: 0,
                }}
              >
                {node.label}
              </span>

              {detail && state !== "pending" && (
                <span
                  className="truncate"
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--text3)",
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  {detail}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {response && (
        <div
          className="flex items-center gap-3"
          style={{ borderTop: "1px solid var(--border)", paddingTop: 6, marginTop: 4, flexShrink: 0 }}
        >
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--text3)" }}>
            {response.llm_calls} LLM call{response.llm_calls !== 1 ? "s" : ""}
            {response.replan_count > 0 && ` · ${response.replan_count} replan${response.replan_count !== 1 ? "s" : ""}`}
          </span>
        </div>
      )}
    </div>
  );
}
