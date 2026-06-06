"""Population-to-channel projection matrix."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pac_framework.generator.config import OscillatorPopulation


def build_projection_matrix(
    populations: list[OscillatorPopulation],
    channels_info: pd.DataFrame,
    mode: str,
) -> np.ndarray:
    """Return a (n_populations, n_channels) float64 weight matrix.

    Entry (p, c) is the weight with which population p contributes to channel c.
    Multiply M.T @ X (where X is (n_populations, n_samples)) to get the
    (n_channels, n_samples) projected signal matrix.

    Modes
    -----
    all_identical  — every entry 1.0; all populations reach all channels.
    region_match   — 1.0 if pop.region matches channel region, else 0.0.

    Raises NotImplementedError for any other mode string.
    """
    n_pop = len(populations)
    n_ch = len(channels_info)

    if n_pop == 0:
        return np.zeros((0, n_ch), dtype=np.float64)
    if n_ch == 0:
        return np.zeros((n_pop, 0), dtype=np.float64)

    if mode == "all_identical":
        return np.ones((n_pop, n_ch), dtype=np.float64)

    if mode == "region_match":
        channel_regions = channels_info["region"].to_numpy()
        M = np.zeros((n_pop, n_ch), dtype=np.float64)
        for p, pop in enumerate(populations):
            M[p] = (channel_regions == pop.region).astype(np.float64)
        return M

    raise NotImplementedError(f"Unknown projection mode: {mode!r}.")
