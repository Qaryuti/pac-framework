"""Unit tests for pac_framework.generator.projection.build_projection_matrix."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pac_framework.generator.config import OscillatorPopulation
from pac_framework.generator.projection import build_projection_matrix


# ── helpers ────────────────────────────────────────────────────────────────


def _pop(id: str, region: str) -> OscillatorPopulation:
    return OscillatorPopulation(
        id=id, center_frequency=6.0, bandwidth=2.0, amplitude=1.0, region=region
    )


def _info(*regions: str) -> pd.DataFrame:
    return pd.DataFrame({"region": list(regions)})


# ── all_identical ──────────────────────────────────────────────────────────


def test_all_identical_all_ones():
    """all_identical mode returns an all-ones matrix regardless of regions."""
    pops = [_pop("theta", "hpc"), _pop("gamma", "ctx")]
    M = build_projection_matrix(pops, _info("hpc", "ctx", "amg", "hpc"), "all_identical")
    assert np.array_equal(M, np.ones((2, 4)))


# ── region_match ───────────────────────────────────────────────────────────


def test_region_match_exact():
    """Single population whose region matches the first two channels only."""
    pops = [_pop("theta", "hippocampus")]
    info = _info("hippocampus", "hippocampus", "amygdala", "amygdala")
    M = build_projection_matrix(pops, info, "region_match")
    assert np.array_equal(M, np.array([[1.0, 1.0, 0.0, 0.0]]))


def test_region_match_no_overlap():
    """Population whose region does not appear in channels → all-zero row."""
    pops = [_pop("theta", "ofc")]
    M = build_projection_matrix(pops, _info("amygdala", "amygdala", "amygdala"), "region_match")
    assert M.shape == (1, 3)
    assert np.all(M == 0.0)


def test_region_match_multi_pop_multi_region():
    """Two populations, four channels interleaved across two regions."""
    pops = [_pop("theta", "hippocampus"), _pop("gamma", "amygdala")]
    info = _info("hippocampus", "amygdala", "hippocampus", "amygdala")
    M = build_projection_matrix(pops, info, "region_match")
    expected = np.array([[1.0, 0.0, 1.0, 0.0],
                          [0.0, 1.0, 0.0, 1.0]])
    assert np.array_equal(M, expected)


# ── edge cases ─────────────────────────────────────────────────────────────


def test_empty_populations_returns_zero_rows():
    """Empty population list → shape (0, n_channels), float64, no error."""
    M = build_projection_matrix([], _info("hpc", "amg", "ctx"), "region_match")
    assert M.shape == (0, 3)
    assert M.dtype == np.float64


def test_empty_populations_all_identical():
    """all_identical with empty populations also returns (0, n_channels)."""
    M = build_projection_matrix([], _info("hpc", "amg"), "all_identical")
    assert M.shape == (0, 2)
    assert M.dtype == np.float64


# ── unknown mode ───────────────────────────────────────────────────────────


def test_unknown_mode_raises_not_implemented():
    """Any unsupported mode raises NotImplementedError naming the mode."""
    pops = [_pop("theta", "hpc")]
    info = _info("hpc")
    with pytest.raises(NotImplementedError, match="region_match_with_anchor_decay"):
        build_projection_matrix(pops, info, "region_match_with_anchor_decay")


def test_completely_unknown_mode_also_raises():
    pops = [_pop("theta", "hpc")]
    info = _info("hpc")
    with pytest.raises(NotImplementedError):
        build_projection_matrix(pops, info, "xyzzy")


# ── dtype and shape guarantee ──────────────────────────────────────────────


def test_dtype_float64_and_shape():
    """Returned matrix is always float64 with shape (n_pops, n_channels)."""
    pops = [_pop("a", "r1"), _pop("b", "r2")]
    info = _info("r1", "r2", "r1")
    for mode in ("all_identical", "region_match"):
        M = build_projection_matrix(pops, info, mode)
        assert M.dtype == np.float64, f"Wrong dtype for mode={mode}"
        assert M.shape == (2, 3), f"Wrong shape for mode={mode}"
