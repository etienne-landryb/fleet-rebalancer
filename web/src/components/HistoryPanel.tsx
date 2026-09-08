"use client";

import { useCallback, useState } from "react";
import { ChevronDown, ChevronRight, History } from "lucide-react";
import { getPlans, type PlanRecord } from "@/lib/api";

export default function HistoryPanel() {
  const [open, setOpen] = useState(false);
  const [plans, setPlans] = useState<PlanRecord[] | null>(null);
  const [loading, setLoading] = useState(false);

  const handleToggle = useCallback(async () => {
    const next = !open;
    setOpen(next);
    if (next && plans === null) {
      setLoading(true);
      try {
        const data = await getPlans(10);
        setPlans(data);
      } catch {
        setPlans([]);
      } finally {
        setLoading(false);
      }
    }
  }, [open, plans]);

  const summary = plans ? `${plans.length} plan${plans.length !== 1 ? "s" : ""} stored` : "";

  return (
    <div className="glass rounded-xl" style={{ overflow: "hidden" }}>
      <button
        onClick={handleToggle}
        className="flex items-center gap-2 w-full"
        style={{
          height: 36,
          padding: "0 12px",
          background: "none",
          border: "none",
          cursor: "pointer",
          color: "var(--text2)",
        }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <History size={12} style={{ color: "var(--text3)" }} />
        <span style={{ fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em" }}>
          History
        </span>
        {!open && summary && (
          <span style={{ fontSize: 10, color: "var(--text3)", fontFamily: "var(--font-mono)" }}>
            · {summary}
          </span>
        )}
      </button>

      <div
        style={{
          maxHeight: open ? 300 : 0,
          overflow: "hidden",
          transition: "max-height 0.3s ease",
        }}
      >
        <div style={{ padding: "0 12px 12px" }}>
          {loading && (
            <div style={{ fontSize: 11, color: "var(--text3)", fontFamily: "var(--font-mono)", padding: "8px 0" }}>
              Loading plans...
            </div>
          )}

          {!loading && plans && plans.length === 0 && (
            <div style={{ fontSize: 11, color: "var(--text3)", fontFamily: "var(--font-mono)", padding: "8px 0" }}>
              No plans yet
            </div>
          )}

          {!loading && plans && plans.length > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontFamily: "var(--font-mono)" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th style={{ ...thStyle }}>Time</th>
                    <th style={{ ...thStyle }}>System</th>
                    <th style={{ ...thStyle }}>Health</th>
                    <th style={{ ...thStyle }}>Bikes</th>
                    <th style={{ ...thStyle }}>Vans</th>
                    <th style={{ ...thStyle }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {plans.map((p) => {
                    const impact = p.projected_impact ?? {};
                    const healthBefore = impact.do_nothing_health != null ? `${(impact.do_nothing_health * 100).toFixed(0)}%` : "—";
                    const healthAfter = impact.planned_health != null ? `${(impact.planned_health * 100).toFixed(0)}%` : "—";
                    const bikes = impact.bikes_moved ?? 0;
                    const vans = p.routes?.length ?? 0;
                    const time = new Date(p.created_at).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                      hour12: false,
                    });
                    return (
                      <tr key={p.id} style={{ borderBottom: "1px solid var(--border)" }}>
                        <td style={{ ...tdStyle }}>{time}</td>
                        <td style={{ ...tdStyle, maxWidth: 80, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.system_id}</td>
                        <td style={{ ...tdStyle }}>
                          <span style={{ color: "var(--text3)" }}>{healthBefore}</span>
                          <span style={{ color: "var(--text3)", margin: "0 2px" }}>→</span>
                          <span style={{ color: "var(--green)" }}>{healthAfter}</span>
                        </td>
                        <td style={{ ...tdStyle }}>{bikes}</td>
                        <td style={{ ...tdStyle }}>{vans}</td>
                        <td style={{ ...tdStyle }}>
                          <span
                            className="rounded-full px-1.5 py-0.5"
                            style={{
                              fontSize: 9,
                              background: p.approval === "approved" ? "var(--green-d)" : "var(--red-d)",
                              color: p.approval === "approved" ? "var(--green)" : "var(--red)",
                            }}
                          >
                            {p.approval}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "4px 6px",
  fontWeight: 600,
  color: "var(--text3)",
  fontSize: 9,
  textTransform: "uppercase",
  letterSpacing: "0.06em",
};

const tdStyle: React.CSSProperties = {
  padding: "5px 6px",
  color: "var(--text2)",
  whiteSpace: "nowrap",
};
