"""Deterministic line-noise synthesis (harmonic sum)."""
from __future__ import annotations

import numpy as np

from pac_framework.generator.config import LineNoisePopulation


def synth_line_noise(
    pop: LineNoisePopulation,
    n_samples: int,
    sfreq: float,
) -> np.ndarray:
    """Sum of per-harmonic sinusoids at absolute µV RMS amplitudes.

    Returns shape (n_samples,), float64.  Deterministic — no RNG.

    Each harmonic k contributes:
        amplitude_per_harmonic[k] * sqrt(2) * cos(2π * harmonics[k] * frequency * t)

    The sqrt(2) factor makes each harmonic's RMS equal to amplitude_per_harmonic[k],
    consistent with the oscillator convention.

    Raises
    ------
    ValueError
        If len(harmonics) != len(amplitude_per_harmonic).
    """
    if len(pop.harmonics) != len(pop.amplitude_per_harmonic):
        raise ValueError(
            f"LineNoisePopulation '{pop.id}': "
            f"len(harmonics)={len(pop.harmonics)} != "
            f"len(amplitude_per_harmonic)={len(pop.amplitude_per_harmonic)}"
        )

    t = np.arange(n_samples) / sfreq
    trace = np.zeros(n_samples, dtype=np.float64)
    for harmonic_idx, amp in zip(pop.harmonics, pop.amplitude_per_harmonic):
        trace += amp * np.sqrt(2.0) * np.cos(
            2.0 * np.pi * harmonic_idx * pop.frequency * t
        )
    return trace
