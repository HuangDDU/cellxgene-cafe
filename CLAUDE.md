# CLAUDE.md — cellxgene-cafe

Cell fate analysis plugin for CZ CELLxGENE Annotate. Injects as a floating jsPanel window via connector scripts.

## Project Overview

- **Host**: native cellxgene (Flask + React/Redux)
- **Plugin**: this project — frontend (React class components + mini Redux store) + backend (Flask blueprint)
- **Communication**: `window.CafeHostBridge` (frontend) + `/api/cafe/*` REST (backend)
- **Key dependency**: `cafe-release` Python package (FateAnnData, trajectory methods, plotting, benchmarks)

## Architecture

```
server/                         Flask blueprint (injected into host app.py)
  cafe_api.py                   Routes: /manifest, /context, /plot/static, /job/*
  cafe_util/                    Backend helpers split by domain
    constants.py                Benchmark metric keys, gene sets
    common.py                   Pure utility functions (color, JSON, type coercion)
    compat.py                   matplotlib/scvelo/fate_anndata patches
    adata.py                    UNS/FateAnnData loading, dataset meta, selection
    plot.py                     Preview building, static rendering, fallback drawing
    data.py                     Data summary, h5ad/trajectory package export
    method.py                   Method catalog, job submission/query/cancel
    explorer.py                 Benchmark, driver genes, gene trends, integrations

scripts/
  inject_server.py              Patches host app.py to register cafe_bp
  inject_client.py              Injects launcher + jsPanel HTML into host templates
  inject_client.html            Injection template (jsPanel bootstrap, HMR dev probe)
  inject_client_js.py           Injects installCafeHostBridge(store) into host index.js
  dev.sh                        Full dev mode: backend + host frontend + plugin HMR
  config.sh                     One-command production install into cellxgene env
  common_env.sh                 Shared helpers (.env loading, Python/npm resolution)

client/src/
  index.jsx                     Entry — mounts React app, exports window.CafePlugin
  components/
    app.jsx                     Root App: reads AppContext, renders TabNav + modules
    TabNav.jsx                  Tab bar
    plot/
      index.jsx                 Pure layout: <DynamicPanel /> + <StaticPanel />
      DynamicPanel/
        index.jsx               Reads AppContext, dispatches setCafeTrajectoryVisible
        TrajectorySetting.jsx   Reads AppContext, dispatches 5 trajectory actions
        TrajectoryPreview.jsx   Reads AppContext for preview SVG data
      StaticPanel/
        index.jsx               Reads AppContext for static plot image URL
    data/index.jsx              Collapsible cards: prior knowledge, trajectory history, cafe results import, embeddings
    explorer/index.jsx          Benchmark table with refresh btn, metric comparison, driver genes, gene trends
    method/index.jsx             Dropdown method selector, smart param inputs, toast notifications
    agent/index.jsx              LLM chat + analysis templates + backend query endpoint
  lib/
    appProvider.jsx             CafeAppProvider — AppContext with manifest/context/bridgeState
    api.js                      Axios client: fetchManifest, fetchContext, buildStaticPlotUrl, job APIs
    cafeStore.js                Mini Redux-like store (createStore, dispatch, subscribe)
    hostBridge.js               Bridge: syncs plugin store ↔ host Redux via window.CafeHostBridge
    cafeHostBridge.js           Host-side bridge installer (injected into cellxgene)
  reducers/
    actions.js                  Action types + creators (CELLXGENE_LAYOUT_CHOICE_SET, CAFE_TRAJECTORY_NAME_SET, ...)
    cellxgene.js                Cellxgene reducer: layoutChoice
    trajectory.js               Trajectory reducer: trajectoryName, display styles
    selectors.js                Default state factory + bridge state selector
    index.js                    Combined reducer
```

## Redux Pattern

- **`AppContext`** (from `appProvider.jsx`) is the single context for `manifest`, `context` (API response), `bridgeState` (Redux state)
- Components use `static contextType = AppContext` and read `this.context`
- Action dispatch happens **inside the component that triggers the interaction**:
  ```jsx
  import { dispatchCafeAction } from "../../../lib/hostBridge";
  import { setCafeTrajectoryName } from "../../../reducers/actions";
  // in render():
  onChange={(e) => dispatchCafeAction(setCafeTrajectoryName(e.target.value))}
  ```
- **Zero action callbacks through props** — no `onSetXxx` prop chains
- `Plot` is the only component with zero Redux/Context imports (pure layout)

## State Shape

```js
{
  cellxgene: {
    layoutChoice: { current: "umap", available: [...], currentDimNames: [...] }
  },
  trajectory: {
    trajectoryName: "ref",
    available: [...],
    showTrajectory: false,
    anchorTrajectory: false,
    trajectoryType: "milestone",
    nodeSize: 2.5,
    edgeWidth: 1,
  }
}
```

## Commands

```bash
# Development (full stack with HMR)
bash scripts/dev.sh

# Production install into cellxgene Python environment
bash scripts/config.sh

# Frontend only
cd client
npm install
npm run build       # production bundle → dist/cafe-plugin.js
npm run dev         # webpack-dev-server with HMR on port 3001
```

## Environment

Copy `.env.example` to `.env` and fill in local paths. Required vars:
- `CELLXGENE_SOURCE_ROOT` — path to cellxgene host source
- `CELLXGENE_CONDA_ENV` — conda env name
- `CELLXGENE_DATASET` — path to .h5ad file with cafe trajectory data

## Commit Conventions

```
feat(scope): description       # new feature
fix(scope): description        # bug fix
refactor(scope): description   # code restructuring
chore: description             # tooling, config
docs: description              # documentation
```

Scopes: `plot`, `data`, `method`, `explorer`, `reducers`, `bridge`, `backend`, `build`

## Branch Strategy

```
main           stable releases
  └── dev      integration branch
       ├── feat/<name>    feature branches
       └── fix/<name>     bug fix branches
```
