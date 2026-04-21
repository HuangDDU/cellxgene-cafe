# cellxgene-cafe

This directory contains the plugin-style integration between Cellxgene and Cafe.

Read the architecture guide first:

- [ARCHITECTURE.md](./ARCHITECTURE.md)

## Current Status

- Plot module: implemented (trajectory selector, show/anchor controls, trajectory type, node/edge sliders, preview, benchmark panel).
- Data module: placeholder.
- Method module: placeholder (job API endpoints are reserved).
- Explorer module: baseline implemented (benchmark view).
- Agent module: placeholder.

## Directory Responsibilities

- `server/cafe_api.py`: route layer for plugin APIs (manifest, context, static plot, gateway status, job placeholders).
- `server/cafe_util.py`: shared backend utility helpers (UNS loading, preview conversion, static rendering, fallback drawing).
- `scripts/inject_client.py`: injects the frontend plugin launcher and panel script into host HTML templates.
- `scripts/inject_client.html`: injection template source loaded by `inject_client.py`.
- `scripts/inject_server.py`: injects backend blueprint registration into host `app.py`.
- `client/src`: plugin frontend application.
- `plugin-manifest`: manifest example and schema.
- `gateway`: placeholder for multi-dataset control plane.

## One-Command Install Into Target Cellxgene Environment

Run inside `cafe-cellxgene/cellxgene-cafe`:

```bash
bash config.sh
```

The script will:

1. Build frontend bundle `dist/cafe-plugin.js`.
2. Copy backend connector files (`server/cafe_api.py` and `server/cafe_util.py`) into the target Cellxgene package path.
3. Copy plugin bundle into host static assets.
4. Inject backend blueprint registration and frontend loader hooks.

Optional environment overrides:

- `CELLXGENE_CONDA_ENV`: target conda env name (default `cellxgene_cafe`).
- `CELLXGENE_PYTHON`: explicit Python path for host resolution.
- `CELLXGENE_HOST_ROOT`: explicit host package root.

After installation, start Cellxgene as usual.

## Developer Mode (Live Frontend + React/Redux Devtools)

Run inside `cafe-cellxgene/cellxgene-cafe`:

```bash
bash dev.sh
```

This mode is designed for iterative development and debugging:

1. Inject plugin hooks into the resolved runtime Cellxgene environment.
2. Keep plugin backend files linked to source (`server/cafe_api.py`, `server/cafe_util.py`).
3. Start plugin frontend watcher in development mode (`webpack --watch`).
4. Start host Cellxgene frontend dev server (development bundle, React/Redux inspection friendly).
5. Patch runtime template to load host dev bundle from the frontend dev server.
6. Launch backend in debug mode from target environment.

Default ports:

- Backend: `5005` (`CELLXGENE_PORT`)
- Frontend dev: `3000` (`CXG_CLIENT_PORT`)

Useful options:

- `CELLXGENE_CONDA_ENV`: target conda env name for runtime injection (default `cafe`).
- `CELLXGENE_SOURCE_ROOT`: host source root for frontend dev server (default `../cellxgene`).
- `CELLXGENE_DATASET`: dataset path used by backend launch.
- `CELLXGENE_FORCE_KILL_PORT`: set `1` to kill conflicting processes on backend/frontend ports.

## Config-Driven Pluginization Model

`config.sh` and `dev.sh` follow the same pluginization contract: host code remains minimally patched via injectors, and plugin behavior is delivered by copied/symlinked connector assets.

### Page Layout Contract

- Main Cellxgene page remains the host rendering surface for embeddings and trajectory overlays.
- Plugin UI is mounted in a floating panel (`jsPanel`) opened by the `Cafe Plugins` launcher button.
- Plot module is split into Dynamics (host-driven overlay control) and Static (backend-rendered figures).

### Host/Plugin Data Interaction Contract

- Plugin to Host: `window.CafeHostBridge.updateTrajectory()` patches host Redux state (`layoutChoice`, `trajectoryChoice`, trajectory style flags).
- Host to Plugin: `window.CafeHostBridge.subscribe()` streams host state changes back to plugin UI.
- Plugin to Backend: plugin calls `/api/cafe/context` and related APIs for normalized trajectory context.
- Backend to Plugin: backend returns manifest/context/preview and static plot images without exposing full host internals.

## Plugin Homepage Screenshot

![cellxgene-cafe](docs/images/cellxgene-cafe.png)