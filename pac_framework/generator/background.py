"""1/f aperiodic background synthesis."""
from __future__ import annotations

import numpy as np

from pac_framework.core.seed_util import derive
from pac_framework.generator.config import BackgroundPopulation


def synth_background(
    pop: BackgroundPopulation,
    n_samples: int,
    sfreq: float,
    seed: int,
) -> np.ndarray:
    """1/f^slope background with optional spectral knee (Lorentzian form).

    Spectral shape:  A(f) = 1 / sqrt(f^slope + knee_hz^slope)
    with f=0 pinned to f=1 to avoid division-by-zero.

    The trace is normalised so std == pop.amplitude (µV).

    Uses derive(seed, "background_innovation") for the white-noise innovation.
    """
    bg_seed = derive(seed, "background_innovation")
    rng = np.random.default_rng(bg_seed)

    noise = rng.standard_normal(n_samples)
    spectrum = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / sfreq)

    # Avoid f=0 singularity: pin DC to the f=1 value
    freqs_safe = freqs.copy()
    freqs_safe[0] = 1.0

    knee = pop.knee_hz
    if knee > 0.0:
        shaping = 1.0 / np.sqrt(freqs_safe ** pop.slope + knee ** pop.slope)
    else:
        shaping = 1.0 / (freqs_safe ** (pop.slope / 2.0))

    colored = np.fft.irfft(spectrum * shaping, n=n_samples).real

    std = colored.std()
    if std > 0.0:
        colored = colored * (pop.amplitude / std)

    return colored.astype(np.float64)
