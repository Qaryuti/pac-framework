"""Tests for G5b — Event-modulated coupling depth.

Covers:
  - build_window_envelope: position, shape, overlap, out-of-bounds clipping
  - apply_phase_to_amplitude: array chi path, length mismatch error
  - apply_couplings: chi_trajectories override, absent key fallback, None default
  - generate_signals: non-constant chi when modulated, constant when not,
    undefined event label raises, max rule, empty config bit-identical
  - manifest migration 0.9.0 → 0.10.0
  - EventModulation field validation bounds
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import pac_framework as pac
from pac_framework.core.manifest_migrations import (
    CURRENT_VERSION,
    load_manifest_with_migrations,
)
from pac_framework.generator.config import (
    EventModulation,
    OscillatorPopulation,
    PhaseToAmpCoupling,
    SessionSpec,
    SignalConfig,
)
from pac_framework.generator.couplings import (
    apply_phase_to_amplitude,
    build_window_envelope,
)
from pac_framework.generator.oscillator import OscillatorOutput
from pac_framework.generator.pipeline import apply_couplings
from pac_framework.generator.runner import build_sessions, generate_signals


# ── helpers ────────────────────────────────────────────────────────────────────

SFREQ = 1000.0
N = 2000


def _channel_info():
    return pd.DataFrame({
        "name": ["LA_00", "LA_01"],
        "type": ["synthetic", "synthetic"],
        "shaft": ["LA", "LA"],
        "region": ["amygdala", "amygdala"],
        "contact_index": [0, 1],
        "position_mm": [0.0, 1.5],
    })


def _sessions_with_events(event_labels=("cue",), duration_sec=5.0):
    spec = SessionSpec(
        date="2026-01-01",
        duration_sec=duration_sec,
        task="test",
        event_catalog=tuple(
            pac.EventClass(name=lbl, rate_hz=2.0, min_gap_sec=0.1)
            for lbl in event_labels
        ),
    )
    return build_sessions("sub-test", seed=0, sfreq=SFREQ,
                          session_specs=[spec], channel_info=_channel_info())


def _osc_out(n=N, carrier_val=1.0, phase_val=0.0):
    return OscillatorOutput(
        carrier=np.full(n, carrier_val, dtype=np.float64),
        phase=np.full(n, phase_val, dtype=np.float64),
    )


def _pac(driver, target, chi=0.5, event_modulations=()):
    return PhaseToAmpCoupling(
        driver=driver, target=target, chi=chi,
        phi_0=0.0, kappa=2.0,
        event_modulations=event_modulations,
    )


# ── build_window_envelope ──────────────────────────────────────────────────────


def test_envelope_zeros_without_events():
    env = build_window_envelope(
        onset_samples=np.array([], dtype=np.int64),
        window_sec=0.5, latency_sec=0.0,
        edge_fraction=0.25, n_samples=N, sfreq=SFREQ,
    )
    assert env.shape == (N,)
    assert np.all(env == 0.0)


def test_envelope_peak_inside_window():
    onset = 100
    window_sec = 0.2  # 200 samples
    env = build_window_envelope(
        onset_samples=np.array([onset], dtype=np.int64),
        window_sec=window_sec, latency_sec=0.0,
        edge_fraction=0.25, n_samples=N, sfreq=SFREQ,
    )
    flat_start = onset + round(0.25 * window_sec * SFREQ)
    flat_end = onset + round(0.75 * window_sec * SFREQ)
    # Flat top should be 1.0
    assert np.allclose(env[flat_start:flat_end], 1.0, atol=1e-10)
    # Outside the window should be 0
    assert env[onset - 1] == 0.0
    assert env[onset + round(window_sec * SFREQ)] == 0.0


def test_envelope_latency_shifts_window():
    onset = 200
    latency_sec = 0.1  # 100 samples
    window_sec = 0.2
    env = build_window_envelope(
        onset_samples=np.array([onset], dtype=np.int64),
        window_sec=window_sec, latency_sec=latency_sec,
        edge_fraction=0.0, n_samples=N, sfreq=SFREQ,
    )
    expected_start = onset + round(latency_sec * SFREQ)
    # Before latency should be zero
    assert np.all(env[:expected_start] == 0.0)
    # At start of window should be 1 (edge_fraction=0 → rectangular)
    assert env[expected_start] == 1.0


def test_envelope_multiple_onsets_combined_by_max():
    env = build_window_envelope(
        onset_samples=np.array([100, 300], dtype=np.int64),
        window_sec=0.1, latency_sec=0.0,
        edge_fraction=0.0, n_samples=N, sfreq=SFREQ,
    )
    assert env[150] == 1.0   # inside first window
    assert env[350] == 1.0   # inside second window
    assert env[250] == 0.0   # between windows


def test_envelope_onset_near_end_clipped():
    """Onset so close to end of signal that window extends past n_samples."""
    env = build_window_envelope(
        onset_samples=np.array([N - 5], dtype=np.int64),
        window_sec=1.0, latency_sec=0.0,
        edge_fraction=0.0, n_samples=N, sfreq=SFREQ,
    )
    assert env.shape == (N,)
    assert env[-5] == 1.0    # first sample in window
    assert env[-1] == 1.0    # capped at signal end


def test_envelope_onset_before_signal_start():
    """Onset + latency before sample 0 → window clipped to start."""
    env = build_window_envelope(
        onset_samples=np.array([0], dtype=np.int64),
        window_sec=0.5, latency_sec=0.0,
        edge_fraction=0.0, n_samples=N, sfreq=SFREQ,
    )
    assert env[0] == 1.0


def test_envelope_output_dtype():
    env = build_window_envelope(
        onset_samples=np.array([10], dtype=np.int64),
        window_sec=0.05, latency_sec=0.0,
        edge_fraction=0.1, n_samples=N, sfreq=SFREQ,
    )
    assert env.dtype == np.float64


def test_envelope_values_in_unit_range():
    env = build_window_envelope(
        onset_samples=np.arange(0, N, 100, dtype=np.int64),
        window_sec=0.15, latency_sec=0.0,
        edge_fraction=0.3, n_samples=N, sfreq=SFREQ,
    )
    assert np.all(env >= 0.0)
    assert np.all(env <= 1.0)


# ── apply_phase_to_amplitude: array chi ───────────────────────────────────────


def test_array_chi_equals_scalar_when_constant():
    """Constant chi array produces the same result as scalar chi."""
    carrier = np.random.default_rng(0).standard_normal(200)
    phase = np.linspace(0, 2 * np.pi, 200)
    chi_scalar = 0.6
    chi_array = np.full(200, chi_scalar)
    out_scalar = apply_phase_to_amplitude(carrier, phase, chi_scalar, 0.0, 2.0)
    out_array = apply_phase_to_amplitude(carrier, phase, chi_array, 0.0, 2.0)
    assert np.allclose(out_scalar, out_array, atol=1e-12)


def test_array_chi_length_mismatch_raises():
    carrier = np.ones(100)
    phase = np.zeros(100)
    chi_wrong = np.ones(50)
    with pytest.raises(ValueError, match="chi array length"):
        apply_phase_to_amplitude(carrier, phase, chi_wrong, 0.0, 2.0)


def test_array_chi_varies_modulation():
    """Time-varying chi produces output that differs from any single scalar."""
    n = 300
    carrier = np.ones(n)
    phase = np.zeros(n)  # phi_0=0 → envelope=1 when chi anything, kappa=0
    # With kappa=2 and phase=0: envelope = (1-chi) + chi * exp(0) = 1 always
    # Use phase = pi to get a non-trivial envelope
    phase[:] = np.pi
    chi_array = np.where(np.arange(n) < 150, 0.2, 0.8)
    out = apply_phase_to_amplitude(carrier, phase, chi_array, 0.0, 2.0)
    # First half should differ from second half since chi differs
    assert not np.allclose(out[:150], out[150:], atol=1e-6)


# ── apply_couplings: chi_trajectories ─────────────────────────────────────────


def test_supplied_trajectory_overrides_scalar_chi():
    """A trajectory in chi_trajectories is used instead of c.chi."""
    n = 100
    outputs = {"driver": _osc_out(n, phase_val=np.pi), "target": _osc_out(n)}
    c = _pac("driver", "target", chi=0.0)   # chi=0 would be no-op

    traj_chi = np.full(n, 0.9)
    key = "driver__to__target"
    result_with = apply_couplings(outputs, [c], chi_trajectories={key: traj_chi})
    result_without = apply_couplings(outputs, [c])   # falls back to c.chi=0

    # chi=0 → no modulation, chi=0.9 → strong modulation at phase=pi
    assert not np.allclose(result_with["target"], result_without["target"])


def test_absent_key_falls_back_to_scalar():
    """Missing trajectory key → falls back to c.chi scalar."""
    n = 100
    outputs = {"A": _osc_out(n, phase_val=np.pi), "B": _osc_out(n)}
    c = _pac("A", "B", chi=0.7)
    result_traj = apply_couplings(outputs, [c], chi_trajectories={})
    result_scalar = apply_couplings(outputs, [c])
    assert np.allclose(result_traj["B"], result_scalar["B"])


def test_none_trajectories_behaves_as_empty_dict():
    n = 100
    outputs = {"A": _osc_out(n), "B": _osc_out(n)}
    c = _pac("A", "B", chi=0.5)
    result_none = apply_couplings(outputs, [c], chi_trajectories=None)
    result_empty = apply_couplings(outputs, [c], chi_trajectories={})
    assert np.allclose(result_none["B"], result_empty["B"])


# ── generate_signals: end-to-end G5b ──────────────────────────────────────────


def _make_sc_with_modulation(event_label: str, peak_chi: float = 0.9) -> SignalConfig:
    theta = OscillatorPopulation(
        id="theta", center_frequency=6.0, bandwidth=2.0,
        amplitude=50.0, region="amygdala",
    )
    gamma = OscillatorPopulation(
        id="gamma", center_frequency=70.0, bandwidth=10.0,
        amplitude=10.0, region="amygdala",
    )
    coupling = PhaseToAmpCoupling(
        driver="theta", target="gamma",
        chi=0.1, phi_0=0.0, kappa=2.0,
        event_modulations=(
            EventModulation(
                event_label=event_label,
                peak_chi=peak_chi,
                window_sec=0.3,
                latency_sec=0.0,
                edge_fraction=0.25,
            ),
        ),
    )
    return SignalConfig(populations=[theta, gamma], couplings=[coupling])


def test_chi_trajectory_non_constant_when_modulated():
    sessions = _sessions_with_events(["cue"], duration_sec=5.0)
    sc = _make_sc_with_modulation("cue")
    result_sessions = generate_signals(sessions, [sc], master_seed=0, subject_name="sub-test")
    chi_traj = result_sessions[0].ground_truth["chi_trajectories"]
    key = "theta__to__gamma"
    assert key in chi_traj
    traj = chi_traj[key]
    # Should not be constant — events lift chi above baseline
    assert not np.allclose(traj, traj[0], atol=1e-6)


def test_chi_trajectory_constant_when_no_modulations():
    sessions = _sessions_with_events(["cue"], duration_sec=3.0)
    theta = OscillatorPopulation(
        id="theta", center_frequency=6.0, bandwidth=2.0, amplitude=50.0, region="amygdala"
    )
    gamma = OscillatorPopulation(
        id="gamma", center_frequency=70.0, bandwidth=10.0, amplitude=10.0, region="amygdala"
    )
    coupling = PhaseToAmpCoupling(driver="theta", target="gamma", chi=0.5)
    sc = SignalConfig(populations=[theta, gamma], couplings=[coupling])
    result = generate_signals(sessions, [sc], master_seed=1, subject_name="sub-test")
    traj = result[0].ground_truth["chi_trajectories"]["theta__to__gamma"]
    assert np.allclose(traj, 0.5)


def test_undefined_event_label_raises():
    sessions = _sessions_with_events(["cue"], duration_sec=3.0)
    sc = _make_sc_with_modulation("nonexistent_event")
    with pytest.raises(ValueError, match="nonexistent_event"):
        generate_signals(sessions, [sc], master_seed=0, subject_name="sub-test")


def test_max_rule_two_modulations():
    """Two overlapping modulations: chi should reach the higher peak_chi."""
    sessions = _sessions_with_events(["cue"], duration_sec=5.0)
    theta = OscillatorPopulation(
        id="theta", center_frequency=6.0, bandwidth=2.0, amplitude=50.0, region="amygdala"
    )
    gamma = OscillatorPopulation(
        id="gamma", center_frequency=70.0, bandwidth=10.0, amplitude=10.0, region="amygdala"
    )
    coupling = PhaseToAmpCoupling(
        driver="theta", target="gamma", chi=0.1, phi_0=0.0, kappa=2.0,
        event_modulations=(
            EventModulation(event_label="cue", peak_chi=0.6,
                            window_sec=0.5, latency_sec=0.0, edge_fraction=0.0),
            EventModulation(event_label="cue", peak_chi=0.95,
                            window_sec=0.5, latency_sec=0.0, edge_fraction=0.0),
        ),
    )
    sc = SignalConfig(populations=[theta, gamma], couplings=[coupling])
    result = generate_signals(sessions, [sc], master_seed=0, subject_name="sub-test")
    traj = result[0].ground_truth["chi_trajectories"]["theta__to__gamma"]
    # The higher peak should win — max lift is (0.95 - 0.1) = 0.85
    assert np.max(traj) > 0.9
    assert np.max(traj) <= 1.0


def test_empty_config_result_bit_identical():
    """Two generate_signals calls with empty SignalConfig produce identical zero channels."""
    sessions = _sessions_with_events(["cue"], duration_sec=2.0)
    sc = SignalConfig()
    out1 = generate_signals(sessions, [sc], master_seed=5, subject_name="sub-test")
    out2 = generate_signals(sessions, [sc], master_seed=5, subject_name="sub-test")
    assert np.array_equal(out1[0].channels.data, out2[0].channels.data)


# ── manifest migration 0.9.0 → 0.10.0 ─────────────────────────────────────────


def _manifest_090_with_pac():
    return {
        "schema_version": "0.9.0",
        "subject_id": "s",
        "gui_config": {
            "name": "s", "seed": 1, "notes": "", "sfreq": 1000,
            "sessions": [{"date": "2026-01-01", "duration_sec": 10.0, "task": "t",
                          "event_catalog": []}],
            "signal": {}, "channel_layout": [], "signals_populated": False,
            "session_signal_configs": [
                {
                    "populations": [],
                    "couplings": [
                        {"kind": "phase_to_amplitude", "driver": "a", "target": "b",
                         "chi": 0.5, "phi_0": 0.0, "kappa": 2.0},
                    ],
                    "projection": {"mode": "region_match", "channel_noise_sd": 3.0},
                }
            ],
        },
        "sessions": [],
    }


def test_migration_090_to_0100_adds_event_modulations():
    m = load_manifest_with_migrations(_manifest_090_with_pac())
    assert m["schema_version"] == "0.10.0"
    coupling = m["gui_config"]["session_signal_configs"][0]["couplings"][0]
    assert "event_modulations" in coupling
    assert coupling["event_modulations"] == []


def test_migration_090_to_0100_idempotent():
    m1 = load_manifest_with_migrations(_manifest_090_with_pac())
    m2 = load_manifest_with_migrations(m1)
    coupling = m2["gui_config"]["session_signal_configs"][0]["couplings"][0]
    assert coupling["event_modulations"] == []


def test_migration_chain_000_to_current():
    minimal = {"subject_id": "x", "gui_config": {"name": "x"}}
    result = load_manifest_with_migrations(minimal)
    assert result["schema_version"] == CURRENT_VERSION


def test_current_version_is_0100():
    assert CURRENT_VERSION == "0.10.0"


# ── EventModulation field validation ──────────────────────────────────────────


def test_event_modulation_valid():
    em = EventModulation(
        event_label="cue", peak_chi=0.8, window_sec=0.5,
        latency_sec=0.1, edge_fraction=0.25,
    )
    assert em.event_label == "cue"
    assert em.peak_chi == 0.8


def test_event_modulation_peak_chi_bounds():
    with pytest.raises(Exception):
        EventModulation(event_label="e", peak_chi=1.1, window_sec=0.5)
    with pytest.raises(Exception):
        EventModulation(event_label="e", peak_chi=-0.1, window_sec=0.5)


def test_event_modulation_window_sec_must_be_positive():
    with pytest.raises(Exception):
        EventModulation(event_label="e", peak_chi=0.5, window_sec=0.0)
    with pytest.raises(Exception):
        EventModulation(event_label="e", peak_chi=0.5, window_sec=-1.0)


def test_event_modulation_latency_non_negative():
    with pytest.raises(Exception):
        EventModulation(event_label="e", peak_chi=0.5, window_sec=1.0, latency_sec=-0.1)


def test_event_modulation_edge_fraction_bounds():
    with pytest.raises(Exception):
        EventModulation(event_label="e", peak_chi=0.5, window_sec=1.0, edge_fraction=0.6)
    with pytest.raises(Exception):
        EventModulation(event_label="e", peak_chi=0.5, window_sec=1.0, edge_fraction=-0.1)


def test_event_modulation_defaults():
    em = EventModulation(event_label="e", peak_chi=0.5, window_sec=1.0)
    assert em.latency_sec == 0.0
    assert em.edge_fraction == 0.25


def test_phase_to_amp_coupling_stores_modulations():
    em = EventModulation(event_label="cue", peak_chi=0.9, window_sec=0.5)
    c = PhaseToAmpCoupling(driver="a", target="b", event_modulations=(em,))
    assert len(c.event_modulations) == 1
    assert c.event_modulations[0].event_label == "cue"
