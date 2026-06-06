"""Tests for pac_framework.generator.scheduling.schedule_class_events."""
from __future__ import annotations

import numpy as np
import pytest

from pac_framework.generator.scheduling import schedule_class_events


def _rng(seed: int = 42) -> np.random.Generator:
    return np.random.default_rng(seed)


# ── basic correctness ──────────────────────────────────────────────────────


def test_empty_output_low_rate():
    """Very low rate × very short duration → expected n ≈ 0 → empty array."""
    # rate_hz * duration = 1e-9; Poisson draw of 1e-9 is 0 with p ≈ 1.
    rng = np.random.default_rng(0)
    result = schedule_class_events(rate_hz=1e-9, min_gap_sec=0.0, duration=1.0, rng=rng)
    assert len(result) == 0


def test_returns_sorted_array():
    rng = _rng(1)
    onsets = schedule_class_events(rate_hz=5.0, min_gap_sec=0.0, duration=10.0, rng=rng)
    assert np.all(np.diff(onsets) >= 0), "output must be sorted ascending"


def test_all_onsets_within_duration():
    duration = 30.0
    rng = _rng(2)
    onsets = schedule_class_events(rate_hz=3.0, min_gap_sec=0.0, duration=duration, rng=rng)
    assert np.all(onsets >= 0.0)
    assert np.all(onsets < duration)


def test_rate_produces_expected_count():
    """Poisson rate * duration should be within 4σ of the empirical mean."""
    rate_hz, duration = 2.0, 200.0
    expected = rate_hz * duration          # 400 events
    std = np.sqrt(expected)                # ≈ 20
    rng = _rng(42)
    onsets = schedule_class_events(
        rate_hz=rate_hz, min_gap_sec=0.0, duration=duration, rng=rng
    )
    assert abs(len(onsets) - expected) < 4 * std, (
        f"Got {len(onsets)} events; expected ~{expected} ± {4 * std:.0f}"
    )


# ── min-gap enforcement ────────────────────────────────────────────────────


def test_min_gap_honored():
    """No two consecutive onsets should be closer than min_gap_sec."""
    min_gap = 0.5
    rng = _rng(10)
    onsets = schedule_class_events(
        rate_hz=10.0, min_gap_sec=min_gap, duration=60.0, rng=rng
    )
    assert len(onsets) > 1, "need multiple events to test gaps"
    gaps = np.diff(onsets)
    assert np.all(gaps >= min_gap - 1e-9), (
        f"min gap violated: smallest gap = {gaps.min():.6f} s"
    )


def test_min_gap_larger_than_duration_gives_at_most_one():
    """If min_gap >= duration, at most one event can be accepted."""
    rng = _rng(99)
    onsets = schedule_class_events(
        rate_hz=100.0, min_gap_sec=60.0, duration=10.0, rng=rng
    )
    assert len(onsets) <= 1


# ── reproducibility ────────────────────────────────────────────────────────


def test_same_seed_identical():
    """Two calls with the same seed must produce bit-identical output."""
    o1 = schedule_class_events(2.0, 0.1, 30.0, np.random.default_rng(7))
    o2 = schedule_class_events(2.0, 0.1, 30.0, np.random.default_rng(7))
    assert np.array_equal(o1, o2)


def test_different_seeds_differ():
    """Different seeds should (with overwhelming probability) differ."""
    o1 = schedule_class_events(2.0, 0.0, 100.0, np.random.default_rng(1))
    o2 = schedule_class_events(2.0, 0.0, 100.0, np.random.default_rng(2))
    assert not np.array_equal(o1, o2)
