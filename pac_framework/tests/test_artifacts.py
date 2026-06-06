"""Tests for G8f sharp-edge artifact synthesis and schema migration."""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path

import numpy as np
import pytest

from pac_framework.generator.config import ArtifactConfig, OscillatorPopulation
from pac_framework.generator.oscillator import synth_oscillator


def _pop(**kw) -> OscillatorPopulation:
    defaults = dict(
        id="test", center_frequency=10.0, bandwidth=2.0, amplitude=10.0, region="hpc"
    )
    defaults.update(kw)
    return OscillatorPopulation(**defaults)


# ── neutral default ────────────────────────────────────────────────────────


def test_artifact_neutral_identical_to_no_artifact():
    """rate_hz=0 produces bit-for-bit identical output to the default (no artifact)."""
    pop_default = _pop()
    pop_zero = _pop(artifact=ArtifactConfig(rate_hz=0.0))
    r1 = synth_oscillator(pop_default, 5_000, 1000.0, 42)
    r2 = synth_oscillator(pop_zero, 5_000, 1000.0, 42)
    assert np.array_equal(r1.carrier, r2.carrier)


# ── artifact presence ──────────────────────────────────────────────────────


def test_artifact_introduces_transients():
    """rate_hz=5 introduces steps whose magnitudes are approximately amplitude_mult × std."""
    pop = _pop(artifact=ArtifactConfig(rate_hz=5.0, amplitude_mult=5.0, width_samples=1))
    result = synth_oscillator(pop, 10_000, 1000.0, 42)
    carrier = result.carrier
    diff = np.abs(np.diff(carrier))
    carrier_std = 10.0  # pop.amplitude
    # At least one jump > 2× carrier_std (from the artifact step)
    assert diff.max() > 2.0 * carrier_std


def test_artifact_count_matches_rate():
    """60 s at rate_hz=2 → approximately 120 artifacts; verify via internal schedule."""
    from pac_framework.core.seed_util import derive
    from pac_framework.generator.scheduling import schedule_class_events

    sfreq = 1000.0
    n = int(60 * sfreq)
    seed = 99
    pop = _pop(
        amplitude=1.0,
        artifact=ArtifactConfig(rate_hz=2.0, amplitude_mult=50.0, width_samples=1),
    )
    # Reproduce the same artifact schedule using the same derived seed
    artifact_seed = derive(seed, "artifact")
    artifact_rng = np.random.default_rng(artifact_seed)
    onsets = schedule_class_events(2.0, 0.0, 60.0, artifact_rng)
    count = len(onsets)
    assert 60 < count < 180, f"Expected ~120 artifacts, got {count}"


def test_artifact_records_internal_seed():
    pop = _pop(artifact=ArtifactConfig(rate_hz=1.0))
    result = synth_oscillator(pop, 500, 1000.0, 7)
    assert "artifact" in result.internal_seeds


# ── schema ─────────────────────────────────────────────────────────────────


def test_artifact_config_defaults():
    cfg = ArtifactConfig()
    assert cfg.rate_hz == 0.0
    assert cfg.amplitude_mult == 3.0
    assert cfg.width_samples == 5


def test_artifact_config_roundtrip():
    pop = _pop(artifact=ArtifactConfig(rate_hz=2.5, amplitude_mult=4.0, width_samples=3))
    data = pop.model_dump()
    restored = OscillatorPopulation.model_validate(data)
    assert restored.artifact.rate_hz == 2.5
    assert restored.artifact.amplitude_mult == 4.0
    assert restored.artifact.width_samples == 3


# ── manifest migration ─────────────────────────────────────────────────────


def test_schema_migration_080_to_090():
    """A 0.8.0 manifest without 'artifact' gains default artifact fields."""
    from pac_framework.core.manifest_migrations import load_manifest_with_migrations

    manifest_080 = {
        "schema_version": "0.8.0",
        "subject_id": "test",
        "gui_config": {
            "name": "test",
            "seed": 42,
            "notes": "",
            "sfreq": 1000.0,
            "sessions": [{"date": "2026-01-01", "duration_sec": 10.0, "task": "t"}],
            "signal": {},
            "channel_layout": [],
            "signals_populated": False,
            "session_signal_configs": [
                {
                    "populations": [
                        {
                            "id": "theta",
                            "kind": "oscillator",
                            "center_frequency": 6.0,
                            "bandwidth": 2.0,
                            "amplitude": 1.0,
                            "region": "hpc",
                            "waveform_shape": {"peak_trough_sharpness": 0.0, "rise_decay_asymmetry": 0.0},
                            "burst": {"mode": "continuous", "rate_hz": 0.5, "duration_cycles_mean": 3.0,
                                      "duration_cycles_sd": 0.5, "refractory_cycles": 1.0},
                            "paf_drift": {"sigma_hz": 0.0, "tau_seconds": 5.0},
                            "seed_tag": "default",
                            # No 'artifact' field — this is the old format
                        }
                    ],
                    "couplings": [],
                    "projection": {"mode": "region_match", "channel_noise_sd": 3.0},
                }
            ],
        },
        "sessions": [],
    }

    migrated = load_manifest_with_migrations(manifest_080)

    assert migrated["schema_version"] == "0.10.0"
    pop_data = migrated["gui_config"]["session_signal_configs"][0]["populations"][0]
    assert "artifact" in pop_data
    assert pop_data["artifact"]["rate_hz"] == 0.0
    assert pop_data["artifact"]["amplitude_mult"] == 3.0
    assert pop_data["artifact"]["width_samples"] == 5
