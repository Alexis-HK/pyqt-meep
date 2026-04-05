# Architecture Refactor Note

## Why this refactor exists
- The current editor model is useful and working, but scene meaning is duplicated across runtime compilation, preview, and script export.
- The package root imports the GUI immediately, which makes plain headless imports fail when Qt is unavailable.
- Current analysis, material, geometry, and source growth would become increasingly cross-cutting if we continue adding features directly onto the flat editor model.

## Old flow
- `ProjectState` is both the editor state and the effective source of truth for runtime/script lowering.
- Runtime compilation happens directly in `meep_gui/specs/builders.py`.
- Preview mixes builder-based FDTD preview with separate MPB-specific reinterpretation.
- Script generation separately reinterprets flat project objects in `meep_gui/script/*`.
- `meep_gui.__init__` imports the GUI entrypoint, so importing package submodules pulls in Qt.

## Target flow
- `ProjectState` remains the editor-facing state for now.
- A typed internal Scene IR becomes the canonical scene definition for current features.
- Analysis execution and script export resolve the active analysis kind through a small recipe registry instead of `if/elif` dispatch.
- Validation combines recipe rules with a capability matrix so runtime and script preparation agree on what is supported, ignored, or forbidden.
- Lowering flows become:
  - `ProjectState -> SceneSpec`
  - `SceneSpec -> runtime compile inputs`
  - `SceneSpec -> preview compile inputs`
  - `SceneSpec -> script emission inputs`
- GUI entrypoints remain explicit; headless subpackages stay importable without Qt.

## Scene IR
- `meep_gui.scene` introduces typed dataclasses for domain, media, geometry, transforms, sources, monitors, symmetries, scene objects, and full scenes.
- The IR is additive-oriented:
  - current simple dielectric / block / circle / current source kinds are fully supported
  - richer future kinds fit through typed extensions instead of `props` dictionaries
- Transmission keeps two separately compiled scenes:
  - scattering scene
  - reference scene

## Later phases
- Phase 0: package/import/test hygiene
- Phase 1: scene IR + adapter + runtime/preview/script rewiring
- Phase 2: recipe layer for analyses
- Phase 3: capability matrix
- Phase 4: typed result artifacts
- Phase 5: light primitive registries

## Current staged status
- Phase 0 is complete:
  - package root stays headless-importable
  - GUI startup remains explicit
- Phase 1 is complete:
  - `meep_gui.scene` is the canonical scene IR for current features
  - runtime, preview, and script export lower through the Scene IR
- Phase 2 is complete:
  - `meep_gui.analysis.recipes` owns the active analysis registry
  - `run_by_kind(...)`, sweep orchestration, and script generation resolve recipes first
- Phase 3 is complete for the current batch:
  - scene-feature extraction and backend/recipe support status are validated during runtime/script preparation
  - `SUPPORTED` proceeds silently, `IGNORED` produces warnings, and `FORBIDDEN` blocks execution/export
- Phase 4 is complete for the current batch:
  - `meep_gui.results` provides a typed artifact layer behind `RunRecord.artifacts` and `RunRecord.plots`
  - output/history rendering now normalizes legacy run outputs through typed artifacts before preview/export dispatch
- Phase 5 is complete for the current batch:
  - `meep_gui.primitives` is the source of truth for current material, geometry, source, and monitor kind metadata
  - model constants remain as compatibility adapters derived from the registries
  - scene/runtime/script/MPB lowering and the current geometry/source/monitor editors now reuse registry metadata/hooks

## Constraints kept during this batch
- No flag-day rewrite
- Existing YAML project schema remains unchanged for current features
- Existing generated-script semantics remain stable for current features
- The Qt editor model remains in place
- `RunRecord`, `ResultArtifact`, and `PlotRecord` remain unchanged as compatibility surfaces in this batch
