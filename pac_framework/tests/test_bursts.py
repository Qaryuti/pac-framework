"""Tests for pac_framework.generator.bursts.burst_envelope (G8b)."""
from __future__ import annotations

import numpy as np
import pytest

from pac_framework.generator.config import BurstConfig
from pac_framework.generator.bursts import burst_envelope


def _rng(seed: int = 42) -> np.random.Generator:
    return np.random.default_rng(seed)


def test_burst_envelope_values_in_0_1():
    cfg = BurstConfig(mode="bursty")
    gate = burst_envelope(cfg, 10.0, 10_000, 1000.0, _rng())
    assert gate.min() >= 0.0
    assert gate.max() <= 1.0


def test_burst_envelope_duty_cycle():
    """~3 cycles / 10 Hz = 0.3 s on at rate 1/s → ~30% duty cycle."""
    cfg = BurstConfig(
        mode="bursty",
        rate_hz=1.0,
        duration_cycles_mean=3.0,
        duration_cycles_sd=0.0,
        refractory_cycles=1.0,
    )
    gate = burst_envelope(cfg, 10.0, 60_000, 1000.0, _rng(7))
    duty = gate.mean()
    assert 0.10 < duty < 0.60, f"Duty cycle {duty:.3f} out of expected range"


def test_burst_no_sharp_transitions():
    """Gate derivative should not exceed 100 / cycle_period."""
    cfg = BurstConfig(mode="bursty", rate_hz=2.0, duration_cycles_mean=5.0)
    sfreq = 1000.0
    fc = 10.0
    gate = burst_envelope(cfg, fc, 10_000, sfreq, _rng(1))
    deriv = np.abs(np.diff(gate))
    cycle_period_samples = sfreq / fc
    assert deriv.max() < 100.0 / cycle_period_samples, (
        f"Max derivative {deriv.max():.4f} suggests sharp transitions"
    )


def test_burst_amplitude_recovered_after_scaling():
    """After amplitude scaling in synth_oscillator, std matches pop.amplitude."""
    from pac_framework.generator.config import OscillatorPopulation
    from pac_framework.generator.oscillator import synth_oscillator

    pop = OscillatorPopulation(
        id="test",
        center_frequency=10.0,
        bandwidth=2.0,
        amplitude=10.0,
        region="hpc",
        burst=BurstConfig(mode="bursty", rate_hz=1.0, duration_cycles_mean=3.0),
    )
    result = synth_oscillator(pop, n_samples=10_000, sfreq=1000.0, seed=42)
    assert abs(result.carrier.std() - 10.0) / 10.0 < 0.01
