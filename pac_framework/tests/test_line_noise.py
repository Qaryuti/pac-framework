"""Tests for pac_framework.generator.line_noise.synth_line_noise (G8e)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pac_framework.core.data_model import Channels, Events, Session, Timeline
from pac_framework.generator.config import (
    LineNoisePopulation,
    OscillatorPopulation,
    SignalConfig,
)
from pac_framework.generator.line_noise import synth_line_noise


# ── helpers ────────────────────────────────────────────────────────────────

N_SAMPLES = 10_240  # 10 s at 1024 Hz — 60/120/180 Hz land on exact bins
SFREQ = 1024.0


def _ln_pop() -> LineNoisePopulation:
    return LineNoisePopulation(
        id="ln0",
        frequency=60.0,
        harmonics=[1, 2, 3],
        amplitude_per_harmonic=[1.0, 0.3, 0.1],
    )


# ── synthesis correctness ──────────────────────────────────────────────────


def test_line_noise_synthesis_fft_peaks():
    """FFT should have dominant peaks exactly at 60, 120, 180 Hz."""
    pop = _ln_pop()
    trace = synth_line_noise(pop, N_SAMPLES, SFREQ)
    assert len(trace) == N_SAMPLES
    assert trace.dtype == np.float64

    freqs = np.fft.rfftfreq(N_SAMPLES, d=1.0 / SFREQ)
    mag = np.abs(np.fft.rfft(trace)) * 2.0 / N_SAMPLES  # amplitude spectrum

    for harmonic_idx, expected_amp in zip([1, 2, 3], [1.0, 0.3, 0.1]):
        target_hz = harmonic_idx * 60.0
        bin_idx = np.argmin(np.abs(freqs - target_hz))
        measured_amp = mag[bin_idx] / np.sqrt(2.0)  # convert to RMS via peak→RMS
        assert abs(measured_amp - expected_amp) / expected_amp < 0.05, (
            f"Harmonic {harmonic_idx} ({target_hz} Hz): "
            f"expected RMS ~{expected_amp}, got {measured_amp:.4f}"
        )

    # Off-harmonic bins should be essentially zero
    mask = np.ones(len(freqs), dtype=bool)
    for h in [1, 2, 3]:
        bin_idx = np.argmin(np.abs(freqs - h * 60.0))
        mask[max(0, bin_idx - 2): bin_idx + 3] = False
    off_harmonic_max = mag[mask].max()
    assert off_harmonic_max < 1e-10, (
        f"Off-harmonic max amplitude {off_harmonic_max:.2e} should be ~0"
    )


def test_line_noise_deterministic():
    """Same config always produces the same trace (no RNG)."""
    pop = _ln_pop()
    a = synth_line_noise(pop, 1000, 1000.0)
    b = synth_line_noise(pop, 1000, 1000.0)
    assert np.array_equal(a, b)


def test_line_noise_mismatched_lists_raises():
    """len(harmonics) != len(amplitude_per_harmonic) raises ValueError."""
    pop = LineNoisePopulation(
        id="bad", frequency=60.0, harmonics=[1, 2], amplitude_per_harmonic=[1.0]
    )
    with pytest.raises(ValueError, match="len"):
        synth_line_noise(pop, 1000, 1000.0)


# ── pipeline integration ───────────────────────────────────────────────────


def test_line_noise_contributes_to_channel_signals():
    """A config with one LN pop produces a non-zero signal even with no oscillators."""
    from pac_framework.core.seed_util import derive
    from pac_framework.generator.pipeline import apply_couplings
    from pac_framework.generator.projection import build_projection_matrix

    n = 1000
    sfreq = 1000.0
    pop = _ln_pop()
    sc = SignalConfig(populations=[pop])

    oscillators = [p for p in sc.populations if p.kind == "oscillator"]
    line_noises = [p for p in sc.populations if p.kind == "line_noise"]

    X = np.zeros((0, n), dtype=np.float64)
    channels_info = pd.DataFrame({
        "name": ["ch0", "ch1"],
        "region": ["r", "r"],
    })
    M = build_projection_matrix(oscillators, channels_info, sc.projection.mode)
    channel_signals = M.T @ X  # zeros

    ln_traces = {p.id: synth_line_noise(p, n, sfreq) for p in line_noises}
    ln_sum = np.sum(list(ln_traces.values()), axis=0)
    channel_signals = channel_signals + ln_sum[None, :]  # broadcast

    # Both channels should have the same non-zero line noise
    assert not np.all(channel_signals == 0)
    assert np.array_equal(channel_signals[0], channel_signals[1])


# ── ground-truth bundle ────────────────────────────────────────────────────


def test_line_noise_ground_truth_roundtrip():
    """line_noise sub-group saves and loads bit-identically."""
    pop = _ln_pop()
    trace = synth_line_noise(pop, 500, 1000.0)

    info = pd.DataFrame({"name": ["ch0"], "type": ["synthetic"]})
    session = Session(
        subject_id="t",
        session_id="s0",
        task="t",
        date_recorded="2026-01-01",
        origin="synthetic",
        timeline=Timeline(sfreq=1000.0, n_samples=500),
        channels=Channels(data=np.zeros((1, 500)), info=info, units="µV"),
        events=Events(
            samples=np.array([], dtype=np.int64),
            labels=tuple(),
            codes=np.array([], dtype=np.int64),
            code_map={},
        ),
        ground_truth={"line_noise": {"ln0": trace}},
    )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "s.h5"
        session.save(path)
        loaded = Session.load(path)

    assert "line_noise" in loaded.ground_truth
    assert np.array_equal(loaded.ground_truth["line_noise"]["ln0"], trace)
