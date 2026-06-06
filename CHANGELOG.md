# Changelog

All notable changes to PAC Framework are documented here.
Versions follow [Semantic Versioning](https://semver.org/).
The manifest schema version tracks the on-disk save format independently of the package version.

---

## [0.10.0] — 2026-06-06

### Added
- **G5b — Event-modulated coupling depth.** `PhaseToAmpCoupling` now accepts
  `event_modulations: tuple[EventModulation, ...]`. Each `EventModulation` lifts
  the baseline `chi` to `peak_chi` following a Tukey (flat-topped raised-cosine)
  window after each event occurrence. Multiple modulations combine by elementwise max.
- `EventModulation` frozen Pydantic model with `event_label`, `peak_chi`,
  `window_sec`, `latency_sec`, `edge_fraction`.
- `build_window_envelope()` in `generator/couplings.py` — Tukey window stamping
  with per-onset max-combination.
- `apply_phase_to_amplitude` now accepts `chi: float | np.ndarray` (array path
  raises `ValueError` on length mismatch).
- `apply_couplings` accepts optional `chi_trajectories: dict[str, np.ndarray]`
  parameter; absent keys fall back to scalar `c.chi`.
- `ground_truth["chi_trajectories"]` is now genuinely time-varying when
  event modulations are configured.
- **GUI** — "Modulation…" button on each PAC coupling row opens
  `CouplingModulationDialog` for editing event modulation entries.
- Manifest schema migration `0.9.0 → 0.10.0` (adds `event_modulations: []`
  to every saved PAC coupling).
- 30 new tests covering all new science-layer and GUI-layer behaviour.

### Schema
- `CURRENT_VERSION` bumped to `"0.10.0"`.

---

## [0.9.0] — 2026-05-25

### Added
- **ArtifactConfig** — sharp-edge transient injection per oscillator population
  (`rate_hz`, `amplitude_mult`, `width_samples`). Default `rate_hz=0` is a no-op.
- `OscillatorPopulation` carries `artifact: ArtifactConfig` field.
- Manifest schema migration `0.8.0 → 0.9.0` (adds default ArtifactConfig to
  every saved oscillator population).
- 17 new tests.

---

## [0.8.0] — 2026-05-20

### Changed
- Per-session signal config replaces the single subject-level config.
  `gui_config.signal_config` → `gui_config.session_signal_configs` (one entry
  per session row). Existing saves migrated automatically.

### Added
- Manifest schema migration `0.7.0 → 0.8.0`.

---

## [0.7.0] — 2026-05-18

### Added
- `signals_populated` flag in the manifest tracks whether channels contain
  generated waveform data or are still zero-filled.
- Default `signal_config` block added to manifest at this version.
- Manifest schema migration `0.6.0 → 0.7.0`.

---

## [0.6.0] — 2026-05-15

### Changed
- Event catalog moved from subject level into each session row.

### Added
- Manifest schema migration `0.5.0 → 0.6.0`.

---

## [0.5.0] — 2026-05-12

### Changed
- Sessions expanded from a uniform spec (`count`, `duration_sec`, `sfreq`)
  into a per-session row list. `sfreq` moved to `gui_config` top level.
- `task_name` and `date_recorded` distributed into each session row.

---

## [0.4.0] — 2026-05-10

### Changed
- `gui_config` restructured from flat keys into nested sub-dicts.
- Subject metadata (`notes`, `task_name`, `date_recorded`) added.

---

## [0.3.0] — 2026-05-08

### Added
- Trial structure placeholder in `gui_config` (later removed from active use).

---

## [0.2.0] — 2026-05-06

### Added
- `event_catalog` in `gui_config`.

---

## [0.1.0] — 2026-05-05

### Added
- `channel_layout` in `gui_config`.
- Initial manifest versioning.

---

## [0.0.0] — 2026-05-01 (initial)

- First working prototype: oscillator synthesis, 1/f background, line noise,
  PAC coupling (scalar chi), region-match projection, HDF5 save/load,
  PyQt6 GUI with three tabs.
