"use client";

import type { TickPhase } from "@/lib/types";

interface JourneyBarProps {
  phase: TickPhase;
  activeStep: number;
  completedSteps: number[];
}

const STEPS = [
  { id: 1, label: "Monitor" },
  { id: 2, label: "Detect risk" },
  { id: 3, label: "Forecast" },
  { id: 4, label: "Plan routes" },
  { id: 5, label: "Compare impact" },
  { id: 6, label: "Approve" },
  { id: 7, label: "Dispatch" },
];

type StepState = "pending" | "active" | "done";

function getStepState(
  stepId: number,
  activeStep: number,
  completedSteps: number[],
): StepState {
  if (completedSteps.includes(stepId)) return "done";
  if (stepId === activeStep) return "active";
  return "pending";
}

export default function JourneyBar({
  phase,
  activeStep,
  completedSteps,
}: JourneyBarProps) {
  return (
    <div
      className="glass flex items-center justify-center gap-0 px-4"
      style={{
        height: 36,
        borderRadius: 0,
        borderLeft: "none",
        borderRight: "none",
        borderTop: "none",
      }}
    >
      {STEPS.map((step, i) => {
        const state = getStepState(step.id, activeStep, completedSteps);

        return (
          <div key={step.id} className="flex items-center">
            {/* Connector line */}
            {i > 0 && (
              <div
                className="mx-1.5"
                style={{
                  width: 24,
                  height: 1,
                  background:
                    state === "done" || state === "active"
                      ? "var(--blue)"
                      : "var(--border2)",
                  transition: "background 0.3s ease",
                }}
              />
            )}

            {/* Step circle + label */}
            <div className="flex items-center gap-1.5">
              <div
                className="flex items-center justify-center rounded-full transition-all"
                style={{
                  width: 18,
                  height: 18,
                  fontSize: 10,
                  fontWeight: 600,
                  fontFamily: "var(--font-mono)",
                  ...(state === "done"
                    ? {
                        background: "var(--green)",
                        color: "white",
                        boxShadow: "0 0 8px var(--green-d)",
                      }
                    : state === "active"
                      ? {
                          background: "var(--blue)",
                          color: "white",
                          boxShadow: "0 0 8px var(--blue-d)",
                        }
                      : {
                          background: "transparent",
                          color: "var(--text3)",
                          border: "1px solid var(--border2)",
                        }),
                }}
              >
                {state === "done" ? "✓" : step.id}
              </div>
              <span
                className="hidden md:inline"
                style={{
                  fontSize: 11,
                  fontWeight: 500,
                  color:
                    state === "active"
                      ? "var(--text)"
                      : state === "done"
                        ? "var(--green)"
                        : "var(--text3)",
                  textDecoration: state === "active" ? "underline" : "none",
                  textUnderlineOffset: 3,
                  transition: "color 0.3s ease",
                }}
              >
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
