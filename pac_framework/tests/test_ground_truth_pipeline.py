"""Tests for G6 ground-truth bundle construction without going through the GUI."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pac_framework.core.seed_util import derive
from pac_framework.generator.config import (
    OscillatorPopulation,
    PhaseToAmpCoupling,
    SignalConfig,
)
from pac_framework.generator.oscillator import synth_oscillator
from pac_framework.generator.pipeline import apply_couplings
from pac_framework.generator.projection import build_projection_matrix


# ── helpers ────────────────────────────────────────────────────────────────

N_SAMPLES = 500
SFREQ = 1000.0
MASTER_SEED = 42


def _make_sc() -> SignalConfig:
    theta = OscillatorPopulation(
        id="theta", center_frequency=6.0, bandwidth=2.0,
        amplitude=50.0, region="hpc",
    )
    gamma = OscillatorPopulation(
        id="gamma", center_frequency=70.0, bandwidth=10.0,
        amplitude=10.0, region="hpc",
    )
    coupling = PhaseToAmpCoupling(
        driver="theta", target="gamma", chi=0.5, phi_0=0.0, kappa=2.0,
    )
    return SignalConfig(populations=[theta, gamma], couplings=[coupling])


def _channels_info() -> pd.DataFrame:
    return pd.DataFrame({
        "name": ["LH_00", "LH_01", "LH_02", "LH_03"],
        "region": ["hpc", "hpc", "hpc", "hpc"],
    })


def _build_bundle(sc: SignalConfig, session_seed: int) -> dict:
    """Mirror the _on_generate bundle construction exactly."""
    oscillators = [p for p in sc.populations if p.kind == "oscillator"]
    channels_info = _channels_info()

    osc_outputs = {}
    for pop in oscillators:
        pop_seed = derive(session_seed, "population", pop.id)
        osc_outputs[pop.id] = synth_oscillator(pop, N_SAMPLES, SFREQ, pop_seed)

    final_carriers = apply_couplings(osc_outputs, sc.couplings)
    M = build_projection_matrix(oscillators, channels_info, sc.projection.mode)

    return {
        "pre_coupling_carriers": {
            pop.id: osc_outputs[pop.id].carrier for pop in oscillators
        },
        "phases": {
            pop.id: osc_outputs[pop.id].phase for pop in oscillators
        },
        "chi_trajectories": {
            f"{c.driver}__to__{c.target}": np.full(N_SAMPLES, c.chi, dtype=np.float64)
            for c in sc.couplings
            if isinstance(c, PhaseToAmpCoupling)
        },
        "projection_matrix": M.astype(np.float64),
        "oscillator_order": [pop.id for pop in oscillators],
        "channel_order": list(channels_info["name"]),
        "signal_config_json": sc.model_dump_json(),
    }, osc_outputs, final_carriers, M


# ── bundle correctness ─────────────────────────────────────────────────────


def test_pre_coupling_carriers_are_pre_coupling():
    """pre_coupling_carriers must equal synth_oscillator output, not post-coupling."""
    sc = _make_sc()
    subject_seed = derive(MASTER_SEED, "subject", "test")
    session_seed = derive(subject_seed, "session", 0)

    bundle, osc_outputs, final_carriers, _ = _build_bundle(sc, session_seed)

    # Pre-coupling carrier must match synth_oscillator directly
    for pop_id in ("theta", "gamma"):
        assert np.array_equal(
            bundle["pre_coupling_carriers"][pop_id],
            osc_outputs[pop_id].carrier,
        ), f"{pop_id} pre-coupling carrier does not match synth_oscillator output"

    # Gamma pre-coupling must differ from post-coupling (PAC was applied)
    assert not np.array_equal(
        bundle["pre_coupling_carriers"]["gamma"],
        final_carriers["gamma"],
    ), "gamma pre- and post-coupling carriers should differ when chi > 0"

    # Theta is not a target so pre-coupling equals post-coupling
    assert np.array_equal(
        bundle["pre_coupling_carriers"]["theta"],
        final_carriers["theta"],
    )


def test_phases_match_synth_oscillator():
    """Phase trajectories in the bundle match the phase field of OscillatorOutput."""
    sc = _make_sc()
    subject_seed = derive(MASTER_SEED, "subject", "test")
    session_seed = derive(subject_seed, "session", 0)

    bundle, osc_outputs, _, _ = _build_bundle(sc, session_seed)

    for pop_id in ("theta", "gamma"):
        assert np.array_equal(
            bundle["phases"][pop_id],
            osc_outputs[pop_id].phase,
        ), f"{pop_id} phase does not match synth_oscillator phase output"


def test_chi_trajectories_constant_at_coupling_chi():
    """chi_trajectories for G6 are constant arrays equal to coupling.chi."""
    sc = _make_sc()
    subject_seed = derive(MASTER_SEED, "subject", "test")
    session_seed = derive(subject_seed, "session", 0)

    bundle, _, _, _ = _build_bundle(sc, session_seed)

    key = "theta__to__gamma"
    assert key in bundle["chi_trajectories"]
    traj = bundle["chi_trajectories"][key]
    assert len(traj) == N_SAMPLES
    assert traj.dtype == np.float64
    assert np.all(traj == 0.5), "chi trajectory should be constant 0.5"


def test_projection_matrix_matches_build_projection_matrix():
    """Stored projection matrix equals direct output of build_projection_matrix."""
    sc = _make_sc()
    oscillators = [p for p in sc.populations if p.kind == "oscillator"]
    channels_info = _channels_info()
    M_direct = build_projection_matrix(oscillators, channels_info, sc.projection.mode)

    subject_seed = derive(MASTER_SEED, "subject", "test")
    session_seed = derive(subject_seed, "session", 0)
    bundle, _, _, M_from_bundle = _build_bundle(sc, session_seed)

    assert np.array_equal(bundle["projection_matrix"], M_direct)
    assert bundle["projection_matrix"].dtype == np.float64


def test_bundle_determinism():
    """Two runs with the same seed produce bit-identical ground-truth bundles."""
    sc = _make_sc()
    subject_seed = derive(MASTER_SEED, "subject", "test")
    session_seed = derive(subject_seed, "session", 0)

    bundle_a, _, _, _ = _build_bundle(sc, session_seed)
    bundle_b, _, _, _ = _build_bundle(sc, session_seed)

    for pop_id in ("theta", "gamma"):
        assert np.array_equal(
            bundle_a["pre_coupling_carriers"][pop_id],
            bundle_b["pre_coupling_carriers"][pop_id],
        )
        assert np.array_equal(bundle_a["phases"][pop_id], bundle_b["phases"][pop_id])

    assert np.array_equal(
        bundle_a["chi_trajectories"]["theta__to__gamma"],
        bundle_b["chi_trajectories"]["theta__to__gamma"],
    )
    assert np.array_equal(bundle_a["projection_matrix"], bundle_b["projection_matrix"])
    assert bundle_a["oscillator_order"] == bundle_b["oscillator_order"]
    assert bundle_a["channel_order"] == bundle_b["channel_order"]
    assert bundle_a["signal_config_json"] == bundle_b["signal_config_json"]
