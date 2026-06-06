"""Tests for pac_framework.generator.config (SignalConfig schema)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from pac_framework.generator.config import (
    BackgroundPopulation,
    BurstConfig,
    LineNoisePopulation,
    OscillatorPopulation,
    PAFDrift,
    PhaseToAmpCoupling,
    PhaseToPhaseCoupling,
    ProjectionConfig,
    SignalConfig,
    WaveformShape,
)

# ── helpers ────────────────────────────────────────────────────────────────


def _theta() -> OscillatorPopulation:
    return OscillatorPopulation(
        id="theta", center_frequency=6.0, bandwidth=2.0, amplitude=1.0, region="hpc"
    )


def _gamma() -> OscillatorPopulation:
    return OscillatorPopulation(
        id="gamma", center_frequency=60.0, bandwidth=10.0, amplitude=0.5, region="hpc"
    )


# ── construction ───────────────────────────────────────────────────────────


def test_empty_config_constructs():
    cfg = SignalConfig()
    assert cfg.populations == []
    assert cfg.couplings == []
    assert cfg.projection.mode == "region_match"
    assert cfg.projection.channel_noise_sd == 3.0


def test_oscillator_defaults():
    pop = _theta()
    assert pop.kind == "oscillator"
    assert pop.waveform_shape.peak_trough_sharpness == 0.0
    assert pop.waveform_shape.rise_decay_asymmetry == 0.0
    assert pop.burst.mode == "continuous"
    assert pop.burst.rate_hz == 0.5
    assert pop.paf_drift.sigma_hz == 0.0
    assert pop.paf_drift.tau_seconds == 5.0
    assert pop.seed_tag == "default"


def test_background_defaults():
    pop = BackgroundPopulation(id="bg")
    assert pop.kind == "background_1f"
    assert pop.slope == 1.5
    assert pop.knee_hz == 0.0
    assert pop.amplitude == 1.0


def test_line_noise_defaults():
    pop = LineNoisePopulation(id="ln")
    assert pop.kind == "line_noise"
    assert pop.frequency == 60.0
    assert pop.harmonics == [1, 2, 3]
    assert pop.amplitude_per_harmonic == [1.0, 0.3, 0.1]


def test_valid_config_with_pac():
    cfg = SignalConfig(
        populations=[_theta(), _gamma()],
        couplings=[PhaseToAmpCoupling(driver="theta", target="gamma")],
    )
    assert len(cfg.populations) == 2
    assert len(cfg.couplings) == 1


def test_valid_config_all_population_types():
    cfg = SignalConfig(
        populations=[
            _theta(),
            BackgroundPopulation(id="bg"),
            LineNoisePopulation(id="ln"),
        ]
    )
    assert len(cfg.populations) == 3


def test_valid_ppc():
    cfg = SignalConfig(
        populations=[_theta(), _gamma()],
        couplings=[
            PhaseToPhaseCoupling(driver="theta", target="gamma", n_to_m_ratio=(3, 2))
        ],
    )
    ppc = cfg.couplings[0]
    assert isinstance(ppc, PhaseToPhaseCoupling)
    assert ppc.n_to_m_ratio == (3, 2)


# ── validation errors ──────────────────────────────────────────────────────


def test_duplicate_population_ids_raise():
    with pytest.raises(ValidationError, match="Duplicate population ids"):
        SignalConfig(
            populations=[
                BackgroundPopulation(id="bg"),
                BackgroundPopulation(id="bg"),
            ]
        )


def test_coupling_missing_driver_raises():
    with pytest.raises(ValidationError, match="not a population id"):
        SignalConfig(
            populations=[_gamma()],
            couplings=[PhaseToAmpCoupling(driver="theta", target="gamma")],
        )


def test_coupling_missing_target_raises():
    with pytest.raises(ValidationError, match="not a population id"):
        SignalConfig(
            populations=[_theta()],
            couplings=[PhaseToAmpCoupling(driver="theta", target="gamma")],
        )


def test_coupling_self_loop_raises():
    with pytest.raises(ValidationError, match="must differ"):
        SignalConfig(
            populations=[_theta()],
            couplings=[PhaseToAmpCoupling(driver="theta", target="theta")],
        )


def test_coupling_cycle_raises():
    with pytest.raises(ValidationError, match="Cycle"):
        SignalConfig(
            populations=[_theta(), _gamma()],
            couplings=[
                PhaseToAmpCoupling(driver="theta", target="gamma"),
                PhaseToAmpCoupling(driver="gamma", target="theta"),
            ],
        )


def test_longer_cycle_raises():
    a = OscillatorPopulation(id="A", center_frequency=4.0, bandwidth=1.0, amplitude=1.0, region="r")
    b = OscillatorPopulation(id="B", center_frequency=8.0, bandwidth=1.0, amplitude=1.0, region="r")
    c = OscillatorPopulation(id="C", center_frequency=40.0, bandwidth=5.0, amplitude=1.0, region="r")
    with pytest.raises(ValidationError, match="Cycle"):
        SignalConfig(
            populations=[a, b, c],
            couplings=[
                PhaseToAmpCoupling(driver="A", target="B"),
                PhaseToAmpCoupling(driver="B", target="C"),
                PhaseToAmpCoupling(driver="C", target="A"),
            ],
        )


# ── field bounds ───────────────────────────────────────────────────────────


def test_oscillator_center_frequency_positive():
    with pytest.raises(ValidationError):
        OscillatorPopulation(id="x", center_frequency=0.0, bandwidth=2.0, amplitude=1.0, region="r")


def test_burst_rate_positive():
    with pytest.raises(ValidationError):
        BurstConfig(rate_hz=0.0)


def test_paf_sigma_nonnegative():
    with pytest.raises(ValidationError):
        PAFDrift(sigma_hz=-0.1)


def test_waveform_shape_bounds():
    with pytest.raises(ValidationError):
        WaveformShape(peak_trough_sharpness=1.5)
    with pytest.raises(ValidationError):
        WaveformShape(rise_decay_asymmetry=-2.0)


def test_pac_chi_bounds():
    with pytest.raises(ValidationError):
        PhaseToAmpCoupling(driver="a", target="b", chi=1.1)


def test_projection_noise_nonnegative():
    with pytest.raises(ValidationError):
        ProjectionConfig(channel_noise_sd=-1.0)


# ── JSON round-trips ───────────────────────────────────────────────────────


def test_roundtrip_empty():
    cfg = SignalConfig()
    restored = SignalConfig.model_validate_json(cfg.model_dump_json())
    assert restored.populations == cfg.populations
    assert restored.couplings == cfg.couplings
    assert restored.projection == cfg.projection


def test_roundtrip_neutral_defaults():
    """Neutral defaults on nested sub-models survive JSON round-trip."""
    cfg = SignalConfig(populations=[_theta()])
    restored = SignalConfig.model_validate_json(cfg.model_dump_json())
    pop = restored.populations[0]
    assert isinstance(pop, OscillatorPopulation)
    assert pop.waveform_shape.peak_trough_sharpness == 0.0
    assert pop.waveform_shape.rise_decay_asymmetry == 0.0
    assert pop.burst.mode == "continuous"
    assert pop.paf_drift.sigma_hz == 0.0
    assert pop.paf_drift.tau_seconds == 5.0


def test_roundtrip_full_config():
    """All three population types + both coupling types survive round-trip."""
    cfg = SignalConfig(
        populations=[
            OscillatorPopulation(
                id="theta",
                center_frequency=6.0,
                bandwidth=2.0,
                amplitude=1.0,
                region="hpc",
                waveform_shape=WaveformShape(peak_trough_sharpness=0.3, rise_decay_asymmetry=-0.1),
                burst=BurstConfig(mode="bursty", rate_hz=1.5, duration_cycles_mean=4.0),
                paf_drift=PAFDrift(sigma_hz=0.5, tau_seconds=3.0),
                seed_tag="my_tag",
            ),
            BackgroundPopulation(id="bg", slope=2.0, knee_hz=1.0, amplitude=0.8),
            LineNoisePopulation(id="ln", frequency=50.0, harmonics=[1, 2], amplitude_per_harmonic=[1.0, 0.2]),
        ],
        couplings=[
            PhaseToAmpCoupling(driver="theta", target="bg", chi=0.7, phi_0=1.57, kappa=3.0),
            PhaseToPhaseCoupling(driver="theta", target="bg", coupling_strength=0.4, delay_ms=20.0, n_to_m_ratio=(2, 1)),
        ],
        projection=ProjectionConfig(mode="all_identical", channel_noise_sd=1.5),
    )

    restored = SignalConfig.model_validate_json(cfg.model_dump_json())

    # populations
    assert len(restored.populations) == 3
    theta = restored.populations[0]
    assert isinstance(theta, OscillatorPopulation)
    assert theta.id == "theta"
    assert theta.center_frequency == 6.0
    assert theta.waveform_shape.peak_trough_sharpness == 0.3
    assert theta.waveform_shape.rise_decay_asymmetry == -0.1
    assert theta.burst.mode == "bursty"
    assert theta.burst.rate_hz == 1.5
    assert theta.paf_drift.sigma_hz == 0.5
    assert theta.seed_tag == "my_tag"

    bg = restored.populations[1]
    assert isinstance(bg, BackgroundPopulation)
    assert bg.slope == 2.0
    assert bg.knee_hz == 1.0

    ln = restored.populations[2]
    assert isinstance(ln, LineNoisePopulation)
    assert ln.frequency == 50.0
    assert ln.harmonics == [1, 2]

    # couplings
    assert len(restored.couplings) == 2
    pac = restored.couplings[0]
    assert isinstance(pac, PhaseToAmpCoupling)
    assert pac.chi == 0.7
    assert pac.phi_0 == 1.57
    assert pac.kappa == 3.0

    ppc = restored.couplings[1]
    assert isinstance(ppc, PhaseToPhaseCoupling)
    assert ppc.n_to_m_ratio == (2, 1)
    assert ppc.delay_ms == 20.0
    assert ppc.coupling_strength == 0.4

    # projection
    assert restored.projection.mode == "all_identical"
    assert restored.projection.channel_noise_sd == 1.5


def test_roundtrip_dict():
    """model_dump() → model_validate() also round-trips correctly."""
    cfg = SignalConfig(populations=[_theta(), BackgroundPopulation(id="bg")])
    data = cfg.model_dump()
    restored = SignalConfig.model_validate(data)
    assert len(restored.populations) == 2
    assert isinstance(restored.populations[0], OscillatorPopulation)
    assert isinstance(restored.populations[1], BackgroundPopulation)
