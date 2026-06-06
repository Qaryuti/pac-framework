"""Manifest schema migration registry.

Each migration is a pure function (dict -> dict). Run them in sequence
via load_manifest_with_migrations() to bring any saved manifest up to
CURRENT_VERSION before the Load handler reads it.

Version history
---------------
0.0.0  initial (no version field, flat gui_config)
0.1.0  added gui_config.channel_layout
0.2.0  added gui_config.event_catalog
0.3.0  added gui_config.trial_structure (later reverted)
0.4.0  restructured gui_config into nested sub-dicts; added subject
       metadata (notes, task_name, date_recorded)
0.5.0  expanded sessions from a uniform spec {count, duration_sec, sfreq}
       into a per-session row list; sfreq moved to gui_config top level;
       task_name and date_recorded moved into each session row
0.6.0  moved event_catalog from subject level into each session row;
       gui_config.event_catalog removed from top level
0.7.0  added gui_config.signals_populated (bool) and gui_config.signal_config
       (default empty SignalConfig) to track generator state
0.8.0  replaced single gui_config.signal_config with per-session list
       gui_config.session_signal_configs; one entry per session row
0.9.0  added ArtifactConfig defaults to every oscillator population
0.10.0 added event_modulations: [] to every PAC coupling entry
"""
from __future__ import annotations

import copy
from datetime import date
from typing import Callable

CURRENT_VERSION = "0.10.0"


# ── individual migrations ──────────────────────────────────────────────────


def _migrate_000_to_010(m: dict) -> dict:
    m.setdefault("gui_config", {}).setdefault("channel_layout", [])
    m["schema_version"] = "0.1.0"
    return m


def _migrate_010_to_020(m: dict) -> dict:
    m.setdefault("gui_config", {}).setdefault("event_catalog", [])
    m["schema_version"] = "0.2.0"
    return m


def _migrate_020_to_030(m: dict) -> dict:
    m.setdefault("gui_config", {}).setdefault("trial_structure", {
        "enabled": False,
        "trial_rate_hz": 0.1,
        "min_trial_gap_sec": 5.0,
        "steps": [],
    })
    m["schema_version"] = "0.3.0"
    return m


def _migrate_030_to_040(m: dict) -> dict:
    """Restructure flat gui_config keys into nested sub-dicts and add
    subject metadata fields (notes, task_name, date_recorded)."""
    cfg = m.get("gui_config", {})
    new_cfg: dict = {}

    # Subject metadata
    new_cfg["name"] = cfg.get("name", m.get("subject_id", "subject_001"))
    new_cfg["seed"] = cfg.get("seed", cfg.get("root_seed", 42))
    new_cfg["notes"] = cfg.get("notes", "")
    new_cfg["task_name"] = cfg.get("task_name", "synthetic")
    new_cfg["date_recorded"] = cfg.get("date_recorded", date.today().isoformat())

    # Sessions sub-dict (flat keys → nested)
    if isinstance(cfg.get("sessions"), dict):
        new_cfg["sessions"] = cfg["sessions"]
    else:
        new_cfg["sessions"] = {
            "count": cfg.get("n_sessions", 3),
            "duration_sec": cfg.get("duration_s", 60.0),
            "sfreq": cfg.get("sfreq", 1000),
        }

    # Signal sub-dict (flat keys → nested)
    if isinstance(cfg.get("signal"), dict):
        new_cfg["signal"] = cfg["signal"]
    else:
        new_cfg["signal"] = {
            "frequency": cfg.get("frequency", 10.0),
            "amplitude": cfg.get("amplitude", 1.0),
            "noise_sd": cfg.get("noise_sigma", cfg.get("noise_sd", 0.05)),
        }

    # Pass-through chunk sections
    new_cfg["channel_layout"] = cfg.get("channel_layout", [])
    new_cfg["event_catalog"] = cfg.get("event_catalog", [])
    new_cfg["trial_structure"] = cfg.get("trial_structure", {
        "enabled": False,
        "trial_rate_hz": 0.1,
        "min_trial_gap_sec": 5.0,
        "steps": [],
    })

    m["gui_config"] = new_cfg
    m["schema_version"] = "0.4.0"
    return m


def _migrate_040_to_050(m: dict) -> dict:
    """Expand the uniform sessions spec into a per-session row list.

    Moves sfreq out of the sessions sub-dict to gui_config top level.
    Distributes the old task_name and date_recorded into each session row.
    """
    cfg = m.get("gui_config", {})
    old_sess = cfg.get("sessions", {})

    if isinstance(old_sess, dict):
        count = int(old_sess.get("count", 3))
        duration_sec = float(old_sess.get("duration_sec", 60.0))
        sfreq = int(old_sess.get("sfreq", 1000))
    else:
        # Already a list from a partially migrated manifest — preserve it.
        cfg["sfreq"] = cfg.get("sfreq", 1000)
        m["gui_config"] = cfg
        m["schema_version"] = "0.5.0"
        return m

    task = cfg.pop("task_name", "synthetic") or "synthetic"
    date_str = cfg.pop("date_recorded", date.today().isoformat())

    cfg["sfreq"] = sfreq
    cfg["sessions"] = [
        {"date": date_str, "duration_sec": duration_sec, "task": task}
        for _ in range(count)
    ]

    m["gui_config"] = cfg
    m["schema_version"] = "0.5.0"
    return m


def _migrate_050_to_060(m: dict) -> dict:
    """Move the subject-level event_catalog into each session row."""
    cfg = m.get("gui_config", {})
    subject_catalog = cfg.pop("event_catalog", [])

    for sess in cfg.get("sessions", []):
        if "event_catalog" not in sess:
            sess["event_catalog"] = [dict(c) for c in subject_catalog]

    m["gui_config"] = cfg
    m["schema_version"] = "0.6.0"
    return m


def _migrate_060_to_070(m: dict) -> dict:
    """Add signals_populated and signal_config with their 0.7.0 defaults."""
    cfg = m.get("gui_config", {})
    cfg.setdefault("signals_populated", False)
    cfg.setdefault("signal_config", {
        "populations": [],
        "couplings": [],
        "projection": {"mode": "region_match", "channel_noise_sd": 3.0},
    })
    m["gui_config"] = cfg
    m["schema_version"] = "0.7.0"
    return m


def _migrate_070_to_080(m: dict) -> dict:
    """Replace the single signal_config with a per-session list."""
    cfg = m.get("gui_config", {})
    old_sc = cfg.pop("signal_config", {
        "populations": [],
        "couplings": [],
        "projection": {"mode": "region_match", "channel_noise_sd": 3.0},
    })
    sessions = cfg.get("sessions", [])
    cfg["session_signal_configs"] = [dict(old_sc) for _ in sessions]
    m["gui_config"] = cfg
    m["schema_version"] = "0.8.0"
    return m


def _migrate_080_to_090(m: dict) -> dict:
    """Add ArtifactConfig defaults to every oscillator population."""
    _artifact_defaults = {"rate_hz": 0.0, "amplitude_mult": 3.0, "width_samples": 5}
    cfg = m.get("gui_config", {})
    for sc in cfg.get("session_signal_configs", []):
        for pop in sc.get("populations", []):
            if pop.get("kind") == "oscillator" and "artifact" not in pop:
                pop["artifact"] = dict(_artifact_defaults)
    m["gui_config"] = cfg
    m["schema_version"] = "0.9.0"
    return m


def _migrate_090_to_0100(m: dict) -> dict:
    """Add event_modulations: [] to every PAC coupling entry."""
    cfg = m.get("gui_config", {})
    for sc in cfg.get("session_signal_configs", []):
        for coupling in sc.get("couplings", []):
            if coupling.get("kind") == "phase_to_amplitude":
                coupling.setdefault("event_modulations", [])
    m["gui_config"] = cfg
    m["schema_version"] = "0.10.0"
    return m


# ── registry ───────────────────────────────────────────────────────────────

_MIGRATIONS: list[tuple[str, str, Callable[[dict], dict]]] = [
    ("0.0.0", "0.1.0", _migrate_000_to_010),
    ("0.1.0", "0.2.0", _migrate_010_to_020),
    ("0.2.0", "0.3.0", _migrate_020_to_030),
    ("0.3.0", "0.4.0", _migrate_030_to_040),
    ("0.4.0", "0.5.0", _migrate_040_to_050),
    ("0.5.0", "0.6.0", _migrate_050_to_060),
    ("0.6.0", "0.7.0", _migrate_060_to_070),
    ("0.7.0", "0.8.0", _migrate_070_to_080),
    ("0.8.0", "0.9.0", _migrate_080_to_090),
    ("0.9.0", "0.10.0", _migrate_090_to_0100),
]


def load_manifest_with_migrations(manifest: dict) -> dict:
    """Return a deep-copy of *manifest* migrated to CURRENT_VERSION.

    Each applied migration is logged to stdout. If the version is
    already current, the manifest is returned unchanged (still a copy).
    Unknown/future versions are returned as-is with a warning.
    """
    m = copy.deepcopy(manifest)
    version = m.get("schema_version", "0.0.0")

    if version == CURRENT_VERSION:
        return m

    for from_ver, to_ver, fn in _MIGRATIONS:
        if version == from_ver:
            print(f"[manifest] migrating schema {from_ver} → {to_ver}")
            m = fn(m)
            version = to_ver
        if version == CURRENT_VERSION:
            break

    if version != CURRENT_VERSION:
        print(
            f"[manifest] warning: expected {CURRENT_VERSION} after migrations,"
            f" ended at {version} — manifest may be from a newer version"
        )

    return m
