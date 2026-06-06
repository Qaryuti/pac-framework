"""Poisson event scheduling for synthetic sessions."""
from __future__ import annotations

import numpy as np


def schedule_class_events(
    rate_hz: float,
    min_gap_sec: float,
    duration: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Return sorted onset times (seconds) for one event class.

    Draws a Poisson count, places candidates uniformly, then greedy-walks
    forward dropping any candidate within min_gap_sec of the last accepted.
    """
    n = int(rng.poisson(rate_hz * duration))
    if n == 0:
        return np.array([], dtype=float)
    candidates = np.sort(rng.uniform(0.0, duration, n))
    accepted: list[float] = []
    last = -np.inf
    for t in candidates:
        if t - last >= min_gap_sec:
            accepted.append(t)
            last = t
    return np.array(accepted, dtype=float)
