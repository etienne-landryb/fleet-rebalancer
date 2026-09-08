# FRONTEND_REBUILD.md — Fleet Rebalancer UI spec

Read this alongside `CLAUDE.md`. This document covers the Next.js operator
console that replaces the original Streamlit UI. Do not touch any file in
`src/rebalancer/agents/`, `src/rebalancer/ml/`, `src/rebalancer/optim/`,
`src/rebalancer/llm/`, or `src/rebalancer/data/`. The Python backend is
complete and correct. Only the presentation layer changes.

---

## 1. Goal

Replace the Streamlit UI with a Next.js operator console. The Python backend
is exposed via a FastAPI bridge (`scripts/local_server.py`) for development and
via Vercel Serverless Functions for deployment.

---

## 2. Architecture

```
Next.js App (web/)
  ├── page.tsx          — layout orchestration, hooks, responsive grid
  ├── components/
  │   ├── Header.tsx        — logo, system selector, theme switcher, Run Analysis
  │   ├── JourneyBar.tsx    — 7-step pipeline with animated states
  │   ├── KpiStrip.tsx      — network health %, starving/saturated counts
  │   ├── MapView.tsx       — Mapbox GL station map + van route overlay
  │   ├── PlanPanel.tsx     — impact grid, work order, routes, approve/reject
  │   ├── AgentTrace.tsx    — decision trace (which nodes fired, branches taken)
  │   ├── StationRiskChart.tsx — top-15 at-risk stations bar chart
  │   └── SystemSelector.tsx   — searchable multi-system dropdown
  ├── hooks/
  │   ├── useTheme.ts       — dark/light/system theme persistence
  │   ├── useGbfs.ts        — GBFS discovery + station data fetching
  │   ├── useSystem.ts      — MobilityData systems.csv catalog
  │   ├── useTick.ts        — graph tick lifecycle + error handling
  │   └── useWindowSize.ts  — responsive breakpoint detection
  └── lib/
      ├── api.ts            — fetch wrappers for the FastAPI backend
      └── types.ts          — TypeScript interfaces
```

---

## 3. Design system

Three-theme glassmorphism with CSS custom properties:

- **Dark** (`data-theme="dark"`): deep navy, blue accents
- **Light** (`data-theme="light"`): frosted white, blue accents
- **System** (`data-theme="system"`): deep indigo, purple accents

Glass utility classes (`.glass`, `.glass2`, `.neumorphic`) use
`backdrop-filter: blur()` with theme-aware borders and shadows.

Map styles follow theme: dark-v11, streets-v12, navigation-night-v1.

---

## 4. Six panels (from CLAUDE.md §9)

1. **KPI strip** — network health %, starving count, saturated count.
   Populated immediately from live GBFS data, before any tick runs.
   Includes a freshness indicator ("Data as of HH:MM UTC · N min ago").

2. **Station health map** — Mapbox GL via react-map-gl. Stations colored
   by risk (starving/healthy/saturated). Filter buttons with counts.
   Van route overlay with street-following directions (Mapbox Directions
   API, chunked for >25 waypoints). Station click popup with fill bar.

3. **Recommended plan panel** — impact assessment table (before/after/delta),
   route cards with collapsible stops, LLM work order with "LLM" badge,
   agent recommendation, approve/reject buttons wired to graph interrupt.
   Idle state shows guidance text explaining the tool.

4. **Decision trace** — all 8 graph nodes with state indicators
   (pending/running/done/hold). Scrollable, compact 28px rows.
   LLM call count and replan count in footer.

5. **At-risk stations chart** — top 15 stations sorted by fill level,
   horizontal bar chart colored by risk. Shows immediately from live data.

6. **System selector** — searchable dropdown of all GBFS systems worldwide
   (from MobilityData's systems.csv). Grouped by country. Selecting a
   system re-centers the map and reloads station data.

---

## 5. Responsive layout

- **Desktop (≥ 1024px)**: map + plan panel side-by-side (1fr 420px),
  trace + risk chart side-by-side (1fr 1fr).
- **Compact (< 1024px)**: all panels stack vertically, content area scrolls.

---

## 6. Error handling

- GBFS fetch failure: error overlay on map with retry button.
- API call failure: red error banner in plan panel, dismissible.
- Errors are never swallowed silently.

---

## 7. Tech stack

- Next.js 16 (App Router, React 19)
- Mapbox GL JS via react-map-gl
- Tailwind CSS v4 with CSS custom properties
- lucide-react for icons
- No charting library — risk chart is CSS-based for consistency
