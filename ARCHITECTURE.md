# cellxgene-cafe Plugin Architecture

This document defines the target architecture for cellxgene-cafe. It is a design reference, not an implementation file. Future development should follow the boundaries, responsibilities, protocols, and migration order described here.

## 1. Goals

- Make trajectory features a plugin window, not a hard-coded Cellxgene sidebar panel.
- Split Plot, Data, Method, Explorer, and Agent into independent modules with a unified protocol.
- Minimize host-side changes to one mount point and one lightweight backend blueprint.
- Keep core computation (data model, methods, plotting, benchmarks) in cafe-release.
- Delegate multi-dataset orchestration to a gateway layer instead of mixing all dataset state in one Cellxgene instance.

## 2. Layered Model

| Layer | Responsibilities | Out of Scope |
| --- | --- | --- |
| Host Cellxgene | Load data, render main UI, expose minimal mount/context | Must not depend on Cafe business protocol details |
| Connector Layer | Injection scripts, plugin blueprint, manifest/context/job routes | Must not implement trajectory algorithms or global business state |
| Plugin Window Layer | Plugin shell, module navigation, forms, charts, local state | Must not depend on host internal component tree |
| cafe-release Platform Layer | FateAnnData, methods, plotting, benchmark, export | Must not care about host React/Redux internals |
| Gateway Layer | Dataset catalog, instance binding, switching, comparison | Must not mix multiple dataset states into one store |

## 3. Recommended File Responsibilities

| Path | Responsibility |
| --- | --- |
| README.md | Project entry with overview and navigation |
| ARCHITECTURE.md | Architecture, protocol contracts, migration path |
| scripts/inject_client.py | Inject plugin loader entry into host HTML |
| scripts/inject_server.py | Register Cafe blueprint into host backend |
| server/cafe_api.py | Plugin route layer (manifest/context/plot/gateway/job placeholders) |
| server/cafe_util.py | Shared backend helper functions and rendering fallbacks |
| client/src/index.jsx | Plugin app mount entry |
| client/src/App.jsx | Plugin window container and module switch |
| client/src/modules/plot | Plot module |
| client/src/modules/data | Data module |
| client/src/modules/method | Method module |
| client/src/modules/explorer | Explorer module |
| client/src/modules/agent | Agent module |
| gateway/ | Multi-dataset control plane |

## 4. Module Design

### 4.1 Plot Module

Plot is the only fully implemented module in stage 1. It should:

- Render trajectory-related views for the main panel (graph, trajectory, pseudotime, stream, velocity, etc.).
- Move control actions into the plugin window (method selector, trajectory type, show/anchor, node size, edge width).
- Support export and layer switching, with plotting state decoupled from raw dataset state.

The Plot module should consume a serializable trajectory spec and should not read deep host Redux internals directly.

### 4.2 Data Module

Data is a placeholder now, but interfaces should be predefined:

- Summarize FateAnnData structure.
- Show dataset metadata, trajectory list, embedding list, color mappings, and source info.
- Provide h5ad export.
- Provide trajectory package export for offline analysis and reproducibility.

Data should expose structured summaries, not the full UNS payload directly.

### 4.3 Method Module

Method is also a placeholder and will become the compute scheduling entry:

- List available methods.
- Show parameter schema for each method.
- Submit method jobs.
- Query job status, results, and logs.
- Support backend runtime options (local Python, conda, Docker, remote services).

Method should orchestrate jobs only; it should not execute algorithms in the frontend.

### 4.4 Explorer Module

Explorer is responsible for downstream result analysis:

- Benchmark tables.
- Method metric comparison views.
- Driver gene and gene trend visualization.
- Future integrations such as GRN, enrichment, and pathway analysis.

Explorer should consume normalized result tables rather than plotting-function-specific objects.

### 4.5 Agent Module

Agent is reserved for skill-based orchestration:

- Display available skills.
- Display skill inputs, outputs, and constraints.
- Map skill calls to Plot/Method/Explorer/Data workflows.
- Future integration for prompts, workflows, tool calls, and analysis templates.

Agent must not access host internals directly; it should operate through connector-exposed context and actions.

## 5. Recommended API Contracts

### 5.1 Manifest

On plugin startup, read manifest first to decide window/module availability.

Recommended shape:

    {
      "apiVersion": 1,
      "dataset": {
        "id": "pancreas_fadata_500",
        "name": "pancreas_fadata_500"
      },
      "plugin": {
        "name": "cafe",
        "version": "0.1.0"
      },
      "capabilities": ["plot", "data", "method", "explorer", "agent"],
      "defaultTab": "plot",
      "modules": [
        {"key": "plot", "enabled": true},
        {"key": "data", "enabled": false},
        {"key": "method", "enabled": false},
        {"key": "explorer", "enabled": false},
        {"key": "agent", "enabled": false}
      ]
    }

### 5.2 Context

Context replaces direct deep reads of `annoMatrix.uns`.

It should include at least:

- Host engine version and dataset identity.
- Active embedding name.
- Available trajectory method/model names.
- Current trajectory layer information.
- Current color mapping and selection state.
- Rendering configuration for overlays.

### 5.3 Trajectory Rendering Contract

Split trajectory responses into three payload types:

- static spec: static images and exports.
- overlay spec: main-panel overlay rendering.
- preview spec: plugin-window network preview.

This allows static and interactive rendering to coexist without overloading one data shape.

### 5.4 Job Contract

Method module should use a standard task API:

- Submit job.
- Query job.
- Cancel job.
- Fetch result.
- Fetch logs.

This protocol must stay UI-independent so multiple runtime backends can implement the same contract.

## 6. Mapping From Existing Code

| Current File | Recommended Direction |
| --- | --- |
| ../cellxgene/client/src/components/rightSidebar/index.js | Keep only generic plugin mount point; remove hard-coded TrajectoryWindow |
| ../cellxgene/client/src/components/trajectoryWindow/* | Migrate as first plugin-window implementation package |
| ../cellxgene/client/src/reducers/trajectory.js | Move out of host global Redux into plugin-local state |
| ../cellxgene/server/data_anndata/anndata_adaptor.py | Keep for data context and serialization compatibility only |
| ../cellxgene/server/app/app.py | Keep only minimal blueprint registration and hook |
| ../cellxgene_VIP/index_template.insert | Use as floating window and docking interaction reference |
| ../../cafe-release/cafe/data/fate_anndata.py | Source of data model |
| ../../cafe-release/cafe/method/* | Method execution core |
| ../../cafe-release/cafe/plot/* | Plotting core |
| ../../cafe-release/cafe/benchmark/* | Benchmark and visualization core |

## 7. Multi-Dataset Gateway

Do not force multi-dataset state into one Cellxgene instance. The gateway should act as control plane and handle:

- Dataset catalog and metadata management.
- Start/bind Cellxgene instances by dataset.
- Build isolated plugin contexts per dataset.
- Aggregate comparison views across datasets.
- Keep each single dataset instance stateless or near-stateless.

Side-by-side comparison should come from gateway-level aggregation, not from sharing one frontend store across datasets.

## 8. Migration Sequence

### Phase 1: Extract Shell Without Behavior Changes

- Keep current trajectory behavior intact.
- Convert TrajectoryWindow into an independent plugin module.
- Extract connector APIs from host components.
- Keep host awareness limited to a generic plugin panel.

### Phase 2: Split Data Protocol

- Let plugin fetch data through manifest and context.
- Replace direct UNS reads with on-demand APIs.
- Keep a compatibility layer while deprecating full UNS access.

### Phase 3: Modular Expansion

- Implement Plot first.
- Add Data.
- Add Method.
- Add Explorer.
- Add Agent.

### Phase 4: Gateway Rollout

- Add dataset catalog.
- Add dataset switching.
- Add comparison views.
- Keep single-dataset plugin deployable independently; orchestrate multi-dataset via gateway.

## 9. Implementation Boundary

Hard rule: after adding the minimal mount point and minimal backend blueprint registration, new Cafe business logic must stay in connector/plugin/gateway areas. Avoid extending host sidebar internals, host graph reducers, or host dataframe loading logic for future Cafe features.

## 10. Suggested Next Steps

Recommended execution order:

- Implement/solidify manifest and context contracts.
- Isolate Plot module cleanly.
- Move window UI from host sidebar to plugin panel.
- Add placeholder pages and contracts for Data/Method/Explorer/Agent.
- Complete gateway integration.

This file is the architecture reference and should be reviewed before implementation changes.
