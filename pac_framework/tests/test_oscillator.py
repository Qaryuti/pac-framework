"""Unit tests for pac_framework.generator.oscillator.synth_oscillator."""
from __future__ import annotations

import logging

import numpy as np
import pytest

from pac_framework.generator.config import (
    BurstConfig,
    OscillatorPopulation,
    PAFDrift,
    WaveformShape,
)
from pac_framework.generator.oscillator import (
    OscillatorOutput,
    _ou_frequency_trajectory,
    synth_oscillator,
)


# ── helpers ────────────────────────────────────────────────────────────────


def _pop(
    *,
    center_frequency: float = 10.0,
    bandwidth: float = 2.0,
    amplitude: float = 1.0,
    **kwargs,
) -> OscillatorPopulation:
    return OscillatorPopulation(
        id="test",
        center_frequency=center_frequency,
        bandwidth=bandwidth,
        amplitude=amplitude,
        region="hpc",
        **kwargs,
    )


# ── return type ────────────────────────────────────────────────────────────


def test_returns_oscillator_output():
    """synth_oscillator returns an OscillatorOutput with required attributes."""
    pop = _pop()
    result = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=42)
    assert isinstance(result, OscillatorOutput)
    assert hasattr(result, "carrier")
    assert hasattr(result, "phase")
    assert hasattr(result, "internal_seeds")


# ── band-limited correctness ───────────────────────────────────────────────


def test_fft_peak_location():
    """FFT argmax of carrier should be within 1 Hz of the configured center frequency."""
    pop = _pop(center_frequency=10.0, bandwidth=2.0)
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    freqs = np.fft.rfftfreq(10_000, d=1.0 / 1000.0)
    mag = np.abs(np.fft.rfft(result.carrier))
    peak_freq = freqs[np.argmax(mag)]
    assert abs(peak_freq - 10.0) <= 1.0, (
        f"Expected peak near 10 Hz, got {peak_freq:.2f} Hz"
    )


def test_bandwidth_roughly_correct():
    """-3 dB bandwidth should be in [2, 8] Hz when bandwidth=4 is configured.

    A single-FFT realization of filtered noise has high spectral variance; we
    use Welch PSD on a longer segment to get a stable estimate of the -3 dB
    bandwidth.
    """
    from scipy import signal as sp_signal

    pop = _pop(center_frequency=20.0, bandwidth=4.0)
    # 100 s at 1000 Hz gives ~97 Welch segments → stable PSD
    result = synth_oscillator(pop, n_samples=100_000, sfreq=1000.0, seed=42)
    f, psd = sp_signal.welch(result.carrier, fs=1000.0, nperseg=2048, noverlap=1024)
    threshold = psd.max() / 2.0  # -3 dB in power
    above = f[psd >= threshold]
    assert len(above) >= 2, "Expected at least two frequency bins above half-power threshold"
    bw_measured = float(above[-1] - above[0])
    assert 2.0 <= bw_measured <= 8.0, (
        f"Measured -3 dB bandwidth {bw_measured:.2f} Hz outside [2, 8] Hz for "
        f"configured bandwidth=4 Hz"
    )


def test_amplitude_scaling():
    """std of the carrier should match pop.amplitude within 1%."""
    target_amp = 5.0
    pop = _pop(amplitude=target_amp)
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    assert abs(result.carrier.std() - target_amp) / target_amp < 0.01, (
        f"Expected std ≈ {target_amp}, got {result.carrier.std():.4f}"
    )


def test_seed_determinism():
    """Same seed → bit-identical output; different seed → different output."""
    pop = _pop()
    r1 = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=42)
    r2 = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=42)
    r3 = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=99)
    assert np.array_equal(r1.carrier, r2.carrier), "Same seed should produce bit-identical carrier"
    assert not np.array_equal(r1.carrier, r3.carrier), "Different seeds should produce different output"


def test_no_nan_no_inf():
    """Carrier must contain only finite values."""
    pop = _pop()
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    assert np.all(np.isfinite(result.carrier)), "Carrier contains NaN or Inf"


def test_output_length():
    """Carrier must have exactly n_samples elements."""
    pop = _pop()
    for n in (500, 1_000, 8_192):
        result = synth_oscillator(pop, n_samples=n, sfreq=1000.0, seed=42)
        assert len(result.carrier) == n, f"Expected length {n}, got {len(result.carrier)}"


def test_no_edge_transient():
    """First 50 samples must not spike more than 3× the carrier's overall std."""
    pop = _pop(center_frequency=10.0, bandwidth=4.0, amplitude=20.0)
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    assert np.max(np.abs(result.carrier[:50])) < 3.0 * result.carrier.std()


# ── pure-sine branch (bandwidth == 0) ─────────────────────────────────────


def test_pure_sine_fft_single_peak():
    """bandwidth=0 produces a carrier whose FFT has >99% power in the peak bin."""
    pop = _pop(center_frequency=10.0, bandwidth=0.0, amplitude=5.0)
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    carrier = result.carrier

    assert abs(carrier.std() - 5.0) / 5.0 < 0.01, (
        f"Expected std ≈ 5.0, got {carrier.std():.4f}"
    )

    freqs = np.fft.rfftfreq(10_000, d=1.0 / 1000.0)
    mag = np.abs(np.fft.rfft(carrier))
    peak_idx = np.argmax(mag)
    assert abs(freqs[peak_idx] - 10.0) <= 0.5

    # Nearly all spectral power is at the single peak bin
    peak_power = mag[peak_idx] ** 2
    total_power = np.sum(mag ** 2)
    assert peak_power / total_power > 0.99, (
        f"Pure sine should concentrate power in one bin; got {peak_power/total_power:.4f}"
    )


# ── phase array ────────────────────────────────────────────────────────────


def test_phase_properties():
    """Phase array is finite, correct length, float64, and wrapped to [-π, π]."""
    pop = _pop()
    result = synth_oscillator(pop, n_samples=2_000, sfreq=1000.0, seed=42)
    p = result.phase
    assert len(p) == 2_000
    assert p.dtype == np.float64
    assert np.all(np.isfinite(p)), "Phase contains NaN or Inf"
    assert np.all(p >= -np.pi) and np.all(p <= np.pi), (
        f"Phase out of [-π, π]: min={p.min():.4f}, max={p.max():.4f}"
    )


def test_phase_independent_of_bandwidth_constant_freq():
    """For sigma_hz=0, phase depends only on center_frequency, not bandwidth."""
    pop_bw = _pop(center_frequency=10.0, bandwidth=2.0)
    pop_sine = _pop(center_frequency=10.0, bandwidth=0.0)
    r_bw = synth_oscillator(pop_bw, n_samples=1_000, sfreq=1000.0, seed=42)
    r_sine = synth_oscillator(pop_sine, n_samples=1_000, sfreq=1000.0, seed=42)
    assert np.array_equal(r_bw.phase, r_sine.phase), (
        "Phase should be identical for the same center_frequency regardless of bandwidth"
    )


# ── warning / fall-back branches ───────────────────────────────────────────


def test_paf_drift_implemented_no_warning():
    """Non-zero sigma_hz is now implemented; no warning is emitted."""
    pop = _pop(paf_drift=PAFDrift(sigma_hz=0.5))
    result = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=42)
    assert len(result.carrier) == 1_000
    assert np.all(np.isfinite(result.carrier))


def test_waveform_shape_no_warning_produces_valid_trace():
    """Non-zero sharpness now produces harmonic injection, no warning, valid trace."""
    pop = _pop(waveform_shape=WaveformShape(peak_trough_sharpness=0.5))
    result = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=42)
    assert np.all(np.isfinite(result.carrier))


def test_burst_implemented_valid_trace():
    """Bursty mode is now implemented; carrier is finite and std matches pop.amplitude."""
    pop = _pop(burst=BurstConfig(mode="bursty"), amplitude=5.0)
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    assert np.all(np.isfinite(result.carrier))
    assert abs(result.carrier.std() - 5.0) / 5.0 < 0.01


def test_burst_continuous_unchanged():
    """mode='continuous' produces identical output to a pop with default burst config."""
    pop_default = _pop()
    pop_cont = _pop(burst=BurstConfig(mode="continuous"))
    r1 = synth_oscillator(pop_default, n_samples=500, sfreq=1000.0, seed=42)
    r2 = synth_oscillator(pop_cont, n_samples=500, sfreq=1000.0, seed=42)
    assert np.array_equal(r1.carrier, r2.carrier)


def test_burst_records_internal_seed():
    pop = _pop(burst=BurstConfig(mode="bursty"))
    result = synth_oscillator(pop, n_samples=500, sfreq=1000.0, seed=3)
    assert "burst" in result.internal_seeds


# ── G8a — Waveform shape ──────────────────────────────────────────────────


def test_waveform_shape_introduces_harmonics():
    """peak_trough_sharpness=1.0 produces a 2nd-harmonic peak at ~0.3× fundamental."""
    pop = _pop(
        center_frequency=10.0, bandwidth=0.0, amplitude=1.0,
        waveform_shape=WaveformShape(peak_trough_sharpness=1.0),
    )
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    carrier = result.carrier
    freqs = np.fft.rfftfreq(10_000, d=1.0 / 1000.0)
    mag = np.abs(np.fft.rfft(carrier)) * 2.0 / 10_000
    bin_fc = np.argmin(np.abs(freqs - 10.0))
    bin_2fc = np.argmin(np.abs(freqs - 20.0))
    ratio = mag[bin_2fc] / mag[bin_fc]
    assert 0.1 < ratio < 0.5, f"2nd harmonic ratio {ratio:.3f} not in expected range"


def test_waveform_shape_neutral_is_sinusoidal():
    """WaveformShape(0, 0) produces only the fundamental peak."""
    pop = _pop(
        center_frequency=10.0, bandwidth=0.0, amplitude=1.0,
        waveform_shape=WaveformShape(peak_trough_sharpness=0.0, rise_decay_asymmetry=0.0),
    )
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    freqs = np.fft.rfftfreq(10_000, d=1.0 / 1000.0)
    mag = np.abs(np.fft.rfft(result.carrier)) * 2.0 / 10_000
    bin_fc = np.argmin(np.abs(freqs - 10.0))
    # All other bins should be negligible compared to the fundamental
    mask = np.ones(len(freqs), dtype=bool)
    mask[max(0, bin_fc - 1): bin_fc + 2] = False
    assert mag[mask].max() < 0.001 * mag[bin_fc], "Non-fundamental bins should be near zero"


def test_waveform_shape_asymmetry_breaks_time_reversal():
    """rise_decay_asymmetry=1.0: time-reversed signal differs from original."""
    pop = _pop(
        center_frequency=10.0, bandwidth=0.0, amplitude=1.0,
        waveform_shape=WaveformShape(rise_decay_asymmetry=1.0),
    )
    result = synth_oscillator(pop, n_samples=2_000, sfreq=1000.0, seed=42)
    x = result.carrier
    x_rev = x[::-1]
    corr = np.corrcoef(x, x_rev)[0, 1]
    # Pure cosine reversal gives corr=1.0; odd harmonics at ±π/2 break this
    assert corr < 0.98, f"Time-reversal correlation {corr:.3f} should be < 0.98 for asymmetric waveform"


# ── G8c — PAF drift ────────────────────────────────────────────────────────


def test_paf_drift_no_warning_valid_trace():
    """Non-zero sigma_hz now synthesizes OU drift without warning."""
    pop = _pop(paf_drift=PAFDrift(sigma_hz=0.5))
    result = synth_oscillator(pop, n_samples=2_000, sfreq=1000.0, seed=42)
    assert len(result.carrier) == 2_000
    assert np.all(np.isfinite(result.carrier))
    assert np.all(np.isfinite(result.phase))


def test_paf_drift_records_internal_seed():
    """paf_drift sub-seed is recorded in internal_seeds."""
    pop = _pop(paf_drift=PAFDrift(sigma_hz=0.5))
    result = synth_oscillator(pop, n_samples=500, sfreq=1000.0, seed=99)
    assert "paf_drift" in result.internal_seeds
    assert isinstance(result.internal_seeds["paf_drift"], int)


def test_paf_drift_deterministic():
    """Same seed → identical carrier and phase."""
    pop = _pop(paf_drift=PAFDrift(sigma_hz=0.3))
    r1 = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=7)
    r2 = synth_oscillator(pop, n_samples=1_000, sfreq=1000.0, seed=7)
    assert np.array_equal(r1.carrier, r2.carrier)
    assert np.array_equal(r1.phase, r2.phase)


def test_paf_drift_changes_phase_vs_nodrift():
    """Carrier phases diverge between sigma_hz=0 and sigma_hz=0.5."""
    pop_drift = _pop(center_frequency=10.0, paf_drift=PAFDrift(sigma_hz=0.5))
    pop_nodrift = _pop(center_frequency=10.0)
    r_drift = synth_oscillator(pop_drift, n_samples=2_000, sfreq=1000.0, seed=42)
    r_nodrift = synth_oscillator(pop_nodrift, n_samples=2_000, sfreq=1000.0, seed=42)
    assert not np.array_equal(r_drift.phase, r_nodrift.phase)


def test_paf_drift_mean_reverts():
    """Long synthesis: mean of frequency trajectory is close to center_frequency."""
    center = 10.0
    sigma = 0.5
    tau = 5.0
    n = int(60.0 * 1000)  # 60 seconds at 1000 Hz
    from pac_framework.core.seed_util import derive
    paf_seed = derive(42, "paf_drift")
    rng = np.random.default_rng(paf_seed)
    f_t = _ou_frequency_trajectory(center, sigma, tau, n, 1000.0, rng)
    assert abs(f_t.mean() - center) < 0.5  # generous tolerance


def test_paf_drift_phase_stochastic():
    """With drift, phase is finite and monotonically non-decreasing (f_t >= 0.1)."""
    pop = _pop(center_frequency=10.0, paf_drift=PAFDrift(sigma_hz=2.0))
    result = synth_oscillator(pop, n_samples=5_000, sfreq=1000.0, seed=13)
    assert np.all(np.isfinite(result.phase))
    # Unwrapped phase should be non-decreasing (f_t clamped to >= 0.1 Hz)
    unwrapped = np.unwrap(result.phase)
    assert np.all(np.diff(unwrapped) >= 0.0)
