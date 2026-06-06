"""Burst gating envelope synthesis."""
from __future__ import annotations

import numpy as np

from pac_framework.generator.config import BurstConfig
from pac_framework.generator.scheduling import schedule_class_events


def burst_envelope(
    burst: BurstConfig,
    center_frequency: float,
    n_samples: int,
    sfreq: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return a smoothed gating envelope, shape (n_samples,), values in [0, 1].

    Burst onset times are drawn from a Poisson process at `burst.rate_hz`
    with a minimum inter-onset gap of `refractory_cycles / center_frequency`
    seconds.  Per-burst duration is drawn from
    Normal(duration_cycles_mean, duration_cycles_sd) / center_frequency,
    clipped to a minimum of one carrier cycle.

    Each burst is tapered with a raised-cosine window over the first and last
    1/8 of its duration to avoid hard edges that would create spurious
    broadband PAC signatures.
    """
    gate = np.zeros(n_samples, dtype=np.float64)
    duration_sec = n_samples / sfreq
    min_gap_sec = burst.refractory_cycles / center_frequency
    one_cycle_sec = 1.0 / center_frequency

    onsets = schedule_class_events(burst.rate_hz, min_gap_sec, duration_sec, rng)

    for onset_time in onsets:
        raw_dur = rng.normal(
            burst.duration_cycles_mean / center_frequency,
            burst.duration_cycles_sd / center_frequency,
        )
        dur_sec = max(raw_dur, one_cycle_sec)
        onset_sample = int(onset_time * sfreq)
        dur_samples = max(1, int(dur_sec * sfreq))
        taper = max(1, dur_samples // 8)

        for k in range(dur_samples):
            s = onset_sample + k
            if s >= n_samples:
                break
            if k < taper:
                val = 0.5 * (1.0 - np.cos(np.pi * k / taper))
            elif k >= dur_samples - taper:
                val = 0.5 * (1.0 - np.cos(np.pi * (dur_samples - k) / taper))
            else:
                val = 1.0
            gate[s] = max(gate[s], val)

    return gate
