"""Tests for pac_framework.core.manifest_migrations."""
from __future__ import annotations

import copy

import pytest

from pac_framework.core.manifest_migrations import (
    CURRENT_VERSION,
    _migrate_000_to_010,
    _migrate_010_to_020,
    _migrate_020_to_030,
    _migrate_030_to_040,
    _migrate_040_to_050,
    _migrate_050_to_060,
    _migrate_060_to_070,
    load_manifest_with_migrations,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _minimal_v0() -> dict:
    """Minimal 0.0.0 manifest (no schema_version, flat gui_config)."""
    return {
        "subject_id": "test_sub",
        "gui_config": {
            "root_seed": 42,
            "n_sessions": 2,
            "duration_s": 30.0,
            "sfreq": 500,
            "frequency": 8.0,
            "amplitude": 2.0,
            "noise_sigma": 0.1,
        },
        "sessions": [],
    }


# ── individual migration steps ─────────────────────────────────────────────


def test_000_to_010_adds_channel_layout():
    m = _migrate_000_to_010({"subject_id": "s", "sessions": []})
    assert m["schema_version"] == "0.1.0"
    assert m["gui_config"]["channel_layout"] == []


def test_000_to_010_preserves_existing_channel_layout():
    existing = [{"shaft": "LA"}]
    m = {"gui_config": {"channel_layout": existing}, "sessions": []}
    out = _migrate_000_to_010(m)
    assert out["gui_config"]["channel_layout"] == existing


def test_010_to_020_adds_event_catalog():
    m = {"schema_version": "0.1.0", "gui_config": {"channel_layout": []}, "sessions": []}
    out = _migrate_010_to_020(m)
    assert out["schema_version"] == "0.2.0"
    assert out["gui_config"]["event_catalog"] == []


def test_020_to_030_adds_trial_structure():
    m = {"schema_version": "0.2.0", "gui_config": {"channel_layout": [], "event_catalog": []}, "sessions": []}
    out = _migrate_020_to_030(m)
    assert out["schema_version"] == "0.3.0"
    ts = out["gui_config"]["trial_structure"]
    assert ts["enabled"] is False
    assert ts["steps"] == []


def test_030_to_040_restructures_flat_keys():
    m = {
        "schema_version": "0.3.0",
        "subject_id": "sub",
        "gui_config": {
            "root_seed": 7,
            "n_sessions": 3,
            "duration_s": 60.0,
            "sfreq": 1000,
            "frequency": 10.0,
            "amplitude": 1.0,
            "noise_sigma": 0.05,
            "channel_layout": [],
            "event_catalog": [{"name": "go"}],
            "trial_structure": {"enabled": False, "steps": []},
        },
        "sessions": [],
    }
    out = _migrate_030_to_040(m)
    cfg = out["gui_config"]
    assert out["schema_version"] == "0.4.0"
    assert cfg["seed"] == 7
    assert cfg["notes"] == ""
    assert cfg["task_name"] == "synthetic"
    assert isinstance(cfg["sessions"], dict)
    assert cfg["sessions"]["count"] == 3
    assert cfg["sessions"]["duration_sec"] == 60.0
    assert cfg["sessions"]["sfreq"] == 1000
    assert isinstance(cfg["signal"], dict)
    assert cfg["signal"]["frequency"] == 10.0
    assert cfg["signal"]["noise_sd"] == 0.05
    assert cfg["event_catalog"][0]["name"] == "go"


def test_040_to_050_expands_sessions_to_list():
    m = {
        "schema_version": "0.4.0",
        "subject_id": "sub",
        "gui_config": {
            "name": "sub", "seed": 42, "notes": "",
            "task_name": "decision", "date_recorded": "2026-01-01",
            "sessions": {"count": 2, "duration_sec": 45.0, "sfreq": 2000},
            "signal": {}, "channel_layout": [], "event_catalog": [],
            "trial_structure": {},
        },
        "sessions": [],
    }
    out = _migrate_040_to_050(m)
    cfg = out["gui_config"]
    assert out["schema_version"] == "0.5.0"
    assert isinstance(cfg["sessions"], list)
    assert len(cfg["sessions"]) == 2
    assert cfg["sessions"][0]["task"] == "decision"
    assert cfg["sessions"][0]["date"] == "2026-01-01"
    assert cfg["sessions"][0]["duration_sec"] == 45.0
    assert cfg["sfreq"] == 2000
    assert "task_name" not in cfg
    assert "date_recorded" not in cfg


def test_050_to_060_moves_catalog_into_sessions():
    catalog = [{"name": "cue", "rate_hz": 0.5, "min_gap_sec": 2.0}]
    m = {
        "schema_version": "0.5.0",
        "gui_config": {
            "sessions": [{"date": "2026-01-01", "duration_sec": 60.0, "task": "A"}],
            "event_catalog": catalog,
        },
        "sessions": [],
    }
    out = _migrate_050_to_060(m)
    cfg = out["gui_config"]
    assert out["schema_version"] == "0.6.0"
    assert "event_catalog" not in cfg
    assert cfg["sessions"][0]["event_catalog"][0]["name"] == "cue"


def test_050_to_060_existing_per_session_catalog_preserved():
    per_session_catalog = [{"name": "already_there"}]
    m = {
        "schema_version": "0.5.0",
        "gui_config": {
            "sessions": [{"date": "2026-01-01", "duration_sec": 60.0, "task": "A",
                          "event_catalog": per_session_catalog}],
            "event_catalog": [{"name": "subject_level"}],
        },
        "sessions": [],
    }
    out = _migrate_050_to_060(m)
    # Per-session catalog already present — should not be overwritten.
    assert out["gui_config"]["sessions"][0]["event_catalog"] == per_session_catalog


def test_060_to_070_adds_signals_populated_and_signal_config():
    m = {
        "schema_version": "0.6.0",
        "gui_config": {
            "sessions": [{"date": "2026-01-01", "duration_sec": 60.0, "task": "A",
                          "event_catalog": []}],
        },
        "sessions": [],
    }
    out = _migrate_060_to_070(m)
    cfg = out["gui_config"]
    assert out["schema_version"] == "0.7.0"
    assert cfg["signals_populated"] is False
    assert cfg["signal_config"]["populations"] == []
    assert cfg["signal_config"]["projection"]["mode"] == "region_match"


# ── full chain ─────────────────────────────────────────────────────────────


def test_full_chain_0_to_current():
    m = load_manifest_with_migrations(_minimal_v0())
    assert m["schema_version"] == CURRENT_VERSION
    cfg = m["gui_config"]
    assert isinstance(cfg["sessions"], list)
    assert "event_catalog" not in cfg          # moved into each session
    assert cfg["signals_populated"] is False
    assert "signal_config" not in cfg                # replaced by per-session list
    assert "session_signal_configs" in cfg
    assert len(cfg["session_signal_configs"]) == len(cfg["sessions"])
    # Each session has its own event_catalog
    for sess in cfg["sessions"]:
        assert "event_catalog" in sess


def test_idempotent_on_current_version():
    """Applying migrations to an already-current manifest is a no-op (deep copy)."""
    from pac_framework.generator.config import SignalConfig
    current = {
        "schema_version": CURRENT_VERSION,
        "subject_id": "x",
        "gui_config": {
            "name": "x", "seed": 1, "notes": "hi", "sfreq": 1000,
            "sessions": [{"date": "2026-01-01", "duration_sec": 60.0, "task": "t",
                          "event_catalog": []}],
            "signal": {"frequency": 10.0, "amplitude": 1.0, "noise_sd": 0.05},
            "channel_layout": [],
            "signals_populated": False,
            "session_signal_configs": [SignalConfig().model_dump()],
        },
        "sessions": [],
    }
    out = load_manifest_with_migrations(current)
    assert out["schema_version"] == CURRENT_VERSION
    assert out["gui_config"]["notes"] == "hi"
    assert out is not current   # returned deep copy, never the original


def test_original_not_mutated():
    original = _minimal_v0()
    original_copy = copy.deepcopy(original)
    load_manifest_with_migrations(original)
    assert original == original_copy


# ── 0.7.0 → 0.8.0 ──────────────────────────────────────────────────────────


def _v7_manifest() -> dict:
    from pac_framework.generator.config import SignalConfig
    return {
        "schema_version": "0.7.0",
        "subject_id": "sub",
        "gui_config": {
            "name": "sub", "seed": 42, "notes": "", "sfreq": 1000,
            "sessions": [
                {"date": "2026-01-01", "duration_sec": 60.0, "task": "A", "event_catalog": []},
                {"date": "2026-01-02", "duration_sec": 30.0, "task": "B", "event_catalog": []},
            ],
            "signal": {},
            "channel_layout": [],
            "signals_populated": False,
            "signal_config": SignalConfig(
                populations=[
                    {"id": "theta", "kind": "oscillator", "center_frequency": 6.0,
                     "bandwidth": 2.0, "amplitude": 50.0, "region": "hpc",
                     "waveform_shape": {"peak_trough_sharpness": 0.0, "rise_decay_asymmetry": 0.0},
                     "burst": {"mode": "continuous", "rate_hz": 0.5,
                               "duration_cycles_mean": 3.0, "duration_cycles_sd": 0.5,
                               "refractory_cycles": 1.0},
                     "paf_drift": {"sigma_hz": 0.0, "tau_seconds": 5.0},
                     "seed_tag": "default"},
                ]
            ).model_dump(),
        },
        "sessions": [],
    }


def test_070_to_080_creates_per_session_list():
    from pac_framework.core.manifest_migrations import _migrate_070_to_080
    m = _v7_manifest()
    out = _migrate_070_to_080(m)
    cfg = out["gui_config"]

    assert out["schema_version"] == "0.8.0"
    assert "signal_config" not in cfg
    assert "session_signal_configs" in cfg
    assert len(cfg["session_signal_configs"]) == 2  # one per session
    # Both entries get the old signal_config's populations
    for sc in cfg["session_signal_configs"]:
        assert sc["populations"][0]["id"] == "theta"


def test_070_to_080_removes_signal_config_key():
    from pac_framework.core.manifest_migrations import _migrate_070_to_080
    out = _migrate_070_to_080(_v7_manifest())
    assert "signal_config" not in out["gui_config"]


def test_070_to_080_idempotent_via_full_chain():
    """Running full migration on a 0.8.0 manifest changes nothing."""
    from pac_framework.generator.config import SignalConfig
    already_080 = {
        "schema_version": "0.8.0",
        "subject_id": "s",
        "gui_config": {
            "name": "s", "seed": 1, "notes": "", "sfreq": 1000,
            "sessions": [{"date": "2026-01-01", "duration_sec": 60.0, "task": "t",
                          "event_catalog": []}],
            "signal": {}, "channel_layout": [], "signals_populated": False,
            "session_signal_configs": [SignalConfig().model_dump()],
        },
        "sessions": [],
    }
    out = load_manifest_with_migrations(already_080)
    # Migrated to current version (0.10.0 is newest)
    assert out["schema_version"] == CURRENT_VERSION
    assert len(out["gui_config"]["session_signal_configs"]) == 1
    assert "signal_config" not in out["gui_config"]
