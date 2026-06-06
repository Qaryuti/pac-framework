"""Unit tests for pac_framework.generator.couplings.apply_phase_to_amplitude."""
from __future__ import annotations

import numpy as np
import pytest

from pac_framework.generator.couplings import apply_phase_to_amplitude


def test_chi_zero_is_no_op():
    """chi=0 → envelope is 1 everywhere → output equals input exactly."""
    carrier = np.linspace(-3.0, 3.0, 200)
    phase = np.linspace(0.0, 2.0 * np.pi, 200)
    result = apply_phase_to_amplitude(carrier, phase, chi=0.0, phi_0=0.0, kappa=2.0)
    assert np.allclose(result, carrier, atol=1e-12)


def test_kappa_zero_uniform_envelope():
    """kappa=0 → exp(0·cos(...) - 0) = 1 → envelope = 1 → output equals input."""
    carrier = np.random.default_rng(0).standard_normal(300)
    phase = np.linspace(0.0, 2.0 * np.pi, 300)
    result = apply_phase_to_amplitude(carrier, phase, chi=0.5, phi_0=0.0, kappa=0.0)
    assert np.allclose(result, carrier, atol=1e-12)


def test_max_envelope_at_preferred_phase():
    """At phi == phi_0 the envelope equals 1 (carrier unchanged)."""
    phi_0 = np.pi / 3.0
    carrier = np.ones(50) * 7.0
    driver_phase = np.full(50, phi_0)
    result = apply_phase_to_amplitude(carrier, driver_phase, chi=0.6, phi_0=phi_0, kappa=3.0)
    # E(phi_0) = (1-chi) + chi * exp(kappa*1 - kappa) = (1-chi) + chi = 1
    assert np.allclose(result, carrier, atol=1e-12)


def test_min_envelope_at_anti_preferred_phase():
    """At phi == phi_0 + pi with chi=1, envelope = exp(-2*kappa)."""
    chi, phi_0, kappa = 1.0, 0.0, 2.0
    carrier = np.ones(100)
    driver_phase = np.full(100, np.pi)  # anti-preferred
    result = apply_phase_to_amplitude(carrier, driver_phase, chi=chi, phi_0=phi_0, kappa=kappa)
    # E = (1-1) + 1 * exp(2*cos(pi) - 2) = exp(-2-2) = exp(-4)
    expected = np.exp(-4.0)
    assert np.allclose(result, expected, rtol=1e-10)


def test_shape_preserved():
    """Output shape equals input shape and dtype is float64."""
    carrier = np.random.default_rng(1).standard_normal(150)
    phase = np.random.default_rng(2).standard_normal(150)
    result = apply_phase_to_amplitude(carrier, phase, chi=0.5, phi_0=0.0, kappa=2.0)
    assert result.shape == carrier.shape
    assert result.dtype == np.float64


def test_inputs_unmodified():
    """Neither target_carrier nor driver_phase is modified in place."""
    carrier = np.ones(80) * 3.0
    phase = np.zeros(80)
    carrier_copy = carrier.copy()
    phase_copy = phase.copy()
    apply_phase_to_amplitude(carrier, phase, chi=0.7, phi_0=0.5, kappa=1.5)
    assert np.array_equal(carrier, carrier_copy)
    assert np.array_equal(phase, phase_copy)
