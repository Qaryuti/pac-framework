"""Unit tests for pac_framework.generator.pipeline.apply_couplings."""
from __future__ import annotations

import numpy as np
import pytest

from pac_framework.generator.config import PhaseToAmpCoupling, PhaseToPhaseCoupling
from pac_framework.generator.oscillator import OscillatorOutput
from pac_framework.generator.pipeline import apply_couplings


# ── helpers ────────────────────────────────────────────────────────────────


def _out(n: int = 100, carrier_val: float = 1.0, phase_val: float = 0.0) -> OscillatorOutput:
    return OscillatorOutput(
        carrier=np.full(n, carrier_val, dtype=np.float64),
        phase=np.full(n, phase_val, dtype=np.float64),
    )


def _pac(driver: str, target: str, chi: float = 0.5, phi_0: float = 0.0, kappa: float = 2.0):
    return PhaseToAmpCoupling(driver=driver, target=target, chi=chi, phi_0=phi_0, kappa=kappa)


def _ppc(driver: str, target: str):
    return PhaseToPhaseCoupling(driver=driver, target=target)


# ── correctness ────────────────────────────────────────────────────────────


def test_empty_couplings_returns_original_carriers():
    """With no couplings every carrier is returned unchanged."""
    outputs = {"a": _out(carrier_val=3.0), "b": _out(carrier_val=7.0)}
    result = apply_couplings(outputs, [])
    assert np.array_equal(result["a"], outputs["a"].carrier)
    assert np.array_equal(result["b"], outputs["b"].carrier)


def test_single_pac_driver_unchanged_target_modulated():
    """PAC: driver carrier is unchanged; target carrier is modulated.

    Use phase = pi (anti-preferred for phi_0=0) so the envelope != 1.
    """
    outputs = {
        "theta": _out(carrier_val=1.0, phase_val=np.pi),  # phase ≠ phi_0=0 → envelope < 1
        "gamma": _out(carrier_val=1.0, phase_val=0.0),
    }
    result = apply_couplings(outputs, [_pac("theta", "gamma", chi=0.5, phi_0=0.0)])
    assert np.array_equal(result["theta"], outputs["theta"].carrier)
    assert not np.array_equal(result["gamma"], outputs["gamma"].carrier)


def test_chained_pac_a_to_b_to_c():
    """A→B→C PAC chain: A unchanged, B and C both modulated."""
    outputs = {
        "A": _out(carrier_val=1.0, phase_val=0.5),
        "B": _out(carrier_val=1.0, phase_val=1.0),
        "C": _out(carrier_val=1.0, phase_val=0.0),
    }
    result = apply_couplings(outputs, [_pac("A", "B"), _pac("B", "C")])
    assert np.array_equal(result["A"], outputs["A"].carrier)
    assert not np.array_equal(result["B"], outputs["B"].carrier)
    assert not np.array_equal(result["C"], outputs["C"].carrier)


def test_ppc_ordering_no_synthesis():
    """PPC edges impose ordering; no synthesis action in G5 — B carrier unchanged."""
    outputs = {
        "A": _out(carrier_val=1.0, phase_val=0.0),
        "B": _out(carrier_val=2.0, phase_val=0.5),
        "C": _out(carrier_val=1.0, phase_val=0.0),
    }
    result = apply_couplings(outputs, [_ppc("A", "B"), _pac("B", "C")])
    assert np.array_equal(result["A"], outputs["A"].carrier)
    assert np.array_equal(result["B"], outputs["B"].carrier)  # PPC — B not synthesised
    assert not np.array_equal(result["C"], outputs["C"].carrier)


# ── error handling ─────────────────────────────────────────────────────────


def test_cycle_raises_runtime_error():
    """A coupling cycle bypassing Pydantic validation raises RuntimeError."""
    outputs = {"A": _out(), "B": _out()}
    with pytest.raises(RuntimeError, match="[Cc]ycle"):
        apply_couplings(outputs, [_pac("A", "B"), _pac("B", "A")])


def test_missing_driver_raises_value_error():
    """Coupling whose driver is not in outputs raises ValueError."""
    outputs = {"B": _out()}  # only B present; A (driver) is missing
    with pytest.raises(ValueError, match="driver"):
        apply_couplings(outputs, [_pac("A", "B")])


def test_missing_target_raises_value_error():
    """Coupling whose target is not in outputs raises ValueError."""
    outputs = {"A": _out()}  # only A present; B (target) is missing
    with pytest.raises(ValueError, match="target"):
        apply_couplings(outputs, [_pac("A", "B")])
