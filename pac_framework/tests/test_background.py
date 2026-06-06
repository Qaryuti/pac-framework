"""Tests for pac_framework.generator.background.synth_background (G8d)."""
from __future__ import annotations

import numpy as np
import pytest

from pac_framework.generator.config import BackgroundPopulation
from pac_framework.generator.background import synth_background


def _bg(**kw) -> BackgroundPopulation:
    return BackgroundPopulation(id="bg0", **kw)


SFREQ = 1024.0
N_60S = int(60 * SFREQ)  # 60 seconds


def test_background_output_shape_and_dtype():
    bg = _bg()
    trace = synth_background(bg, 1000, 1000.0, 42)
    assert len(trace) == 1000
    assert trace.dtype == np.float64


def test_background_amplitude_calibration():
    """std of the output should be pop.amplitude (exactly, after normalization)."""
    bg = _bg(amplitude=5.0)
    trace = synth_background(bg, 10_000, SFREQ, 42)
    assert abs(trace.std() - 5.0) / 5.0 < 0.01


def test_background_deterministic():
    bg = _bg()
    a = synth_background(bg, 5_000, SFREQ, 42)
    b = synth_background(bg, 5_000, SFREQ, 42)
    assert np.array_equal(a, b)


def test_background_spectrum_slope():
    """Log-log PSD slope over 5–200 Hz should be ≈ -slope (within 0.15)."""
    from scipy import signal as sp_signal

    bg = _bg(slope=1.5, knee_hz=0.0, amplitude=1.0)
    trace = synth_background(bg, N_60S, SFREQ, 7)

    f, psd = sp_signal.welch(trace, fs=SFREQ, nperseg=4096, noverlap=2048)
    mask = (f >= 5) & (f <= 200) & (psd > 0)
    log_f = np.log10(f[mask])
    log_p = np.log10(psd[mask])
    slope_fit = np.polyfit(log_f, log_p, 1)[0]
    expected = -1.5
    assert abs(slope_fit - expected) < 0.15, (
        f"PSD log-log slope {slope_fit:.3f} != expected {expected}"
    )


def test_background_knee_flattens_low_frequencies():
    """With knee_hz=10, PSD should be flatter below 10 Hz than above."""
    from scipy import signal as sp_signal

    bg = _bg(slope=2.0, knee_hz=10.0, amplitude=1.0)
    trace = synth_background(bg, N_60S, SFREQ, 3)
    f, psd = sp_signal.welch(trace, fs=SFREQ, nperseg=4096, noverlap=2048)

    lo_mask = (f >= 1) & (f <= 5)
    hi_mask = (f >= 50) & (f <= 200)

    lo_f, lo_p = np.log10(f[lo_mask]), np.log10(psd[lo_mask])
    hi_f, hi_p = np.log10(f[hi_mask]), np.log10(psd[hi_mask])

    slope_lo = np.polyfit(lo_f, lo_p, 1)[0]
    slope_hi = np.polyfit(hi_f, hi_p, 1)[0]
    # Below knee: flatter (less negative slope) than above knee
    assert slope_lo > slope_hi, (
        f"Low-freq slope {slope_lo:.2f} should be > high-freq slope {slope_hi:.2f}"
    )
