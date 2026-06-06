"""Signal configuration and experiment-design schema for the PAC generator.

All models are frozen (immutable after construction). Default-constructed
SignalConfig() is valid and produces an empty — but well-formed — config.

Experiment design (EventClass, SessionSpec) lives here so the generator can
be used without the GUI:

    from pac_framework.generator.config import EventClass, SessionSpec, SignalConfig
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventClass(BaseModel):
    """One class of experimental events, scheduled by a Poisson process.

    Example::

        cue = EventClass(name="cue_onset", rate_hz=0.5, min_gap_sec=2.0)
    """

    model_config = ConfigDict(frozen=True)

    name: str
    rate_hz: float = Field(gt=0.0)
    min_gap_sec: float = Field(0.0, ge=0.0)


class SessionSpec(BaseModel):
    """Specification for building a single synthetic recording session.

    Example::

        spec = SessionSpec(
            date="2026-01-01",
            duration_sec=120.0,
            task="rest",
            event_catalog=(EventClass("cue_onset", rate_hz=0.5),),
        )
    """

    model_config = ConfigDict(frozen=True)

    date: str
    duration_sec: float = Field(gt=0.0)
    task: str = "synthetic"
    event_catalog: tuple[EventClass, ...] = ()


class WaveformShape(BaseModel):
    """Non-sinusoidal waveform via harmonic injection.

    Neutral defaults (0, 0) produce a pure sinusoidal carrier.
    """

    model_config = ConfigDict(frozen=True)

    peak_trough_sharpness: float = Field(0.0, ge=-1.0, le=1.0)
    rise_decay_asymmetry: float = Field(0.0, ge=-1.0, le=1.0)


class BurstConfig(BaseModel):
    """Intermittent bursting envelope.

    mode='continuous' produces an uninterrupted carrier.
    """

    model_config = ConfigDict(frozen=True)

    mode: Literal["continuous", "bursty"] = "continuous"
    rate_hz: float = Field(0.5, gt=0.0)
    duration_cycles_mean: float = Field(3.0, gt=0.0)
    duration_cycles_sd: float = Field(0.5, ge=0.0)
    refractory_cycles: float = Field(1.0, ge=0.0)


class PAFDrift(BaseModel):
    """Ornstein-Uhlenbeck drift of the center frequency.

    sigma_hz=0 (default) produces a constant center frequency.
    """

    model_config = ConfigDict(frozen=True)

    sigma_hz: float = Field(0.0, ge=0.0)
    tau_seconds: float = Field(5.0, gt=0.0)


class ArtifactConfig(BaseModel):
    """Sharp-edge transients injected after amplitude scaling.

    rate_hz=0 (default) produces no artifacts.
    """

    model_config = ConfigDict(frozen=True)

    rate_hz: float = Field(0.0, ge=0.0)
    amplitude_mult: float = Field(3.0, gt=0.0)
    width_samples: int = Field(5, gt=0)


class OscillatorPopulation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: Literal["oscillator"] = "oscillator"
    center_frequency: float = Field(gt=0.0)
    bandwidth: float = Field(ge=0.0)
    amplitude: float = Field(gt=0.0)
    region: str
    waveform_shape: WaveformShape = Field(default_factory=WaveformShape)
    burst: BurstConfig = Field(default_factory=BurstConfig)
    paf_drift: PAFDrift = Field(default_factory=PAFDrift)
    artifact: ArtifactConfig = Field(default_factory=ArtifactConfig)
    seed_tag: str = "default"


class BackgroundPopulation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: Literal["background_1f"] = "background_1f"
    slope: float = Field(1.5, gt=0.0)
    knee_hz: float = Field(0.0, ge=0.0)
    amplitude: float = Field(1.0, gt=0.0)
    seed_tag: str = "default"


class LineNoisePopulation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: Literal["line_noise"] = "line_noise"
    frequency: float = Field(60.0, gt=0.0)
    harmonics: list[int] = Field(default_factory=lambda: [1, 2, 3])
    amplitude_per_harmonic: list[float] = Field(
        default_factory=lambda: [1.0, 0.3, 0.1]
    )
    seed_tag: str = "default"


class EventModulation(BaseModel):
    """Time-varying chi lift driven by a named event class.

    For each event occurrence the chi envelope rises from the coupling's
    baseline chi to peak_chi following a Tukey (flat-topped raised-cosine)
    window of width window_sec, starting latency_sec after the event onset.
    Multiple modulations are combined by elementwise max then added to the
    baseline chi (clamped to [0, 1]).
    """

    model_config = ConfigDict(frozen=True)

    event_label: str
    peak_chi: float = Field(ge=0.0, le=1.0)
    window_sec: float = Field(gt=0.0)
    latency_sec: float = Field(0.0, ge=0.0)
    edge_fraction: float = Field(0.25, ge=0.0, le=0.5)


class PhaseToAmpCoupling(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["phase_to_amplitude"] = "phase_to_amplitude"
    driver: str
    target: str
    chi: float = Field(0.5, ge=0.0, le=1.0)
    phi_0: float = Field(0.0)  # radians; UI converts to/from degrees
    kappa: float = Field(2.0, ge=0.0)
    event_modulations: tuple[EventModulation, ...] = ()


class PhaseToPhaseCoupling(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Literal["phase_to_phase"] = "phase_to_phase"
    driver: str
    target: str
    coupling_strength: float = Field(0.3, ge=0.0, le=1.0)
    delay_ms: float = Field(15.0, ge=0.0)
    n_to_m_ratio: tuple[int, int] = (1, 1)


# Discriminated unions — Pydantic dispatches on the 'kind' field.
Population = Annotated[
    Union[OscillatorPopulation, BackgroundPopulation, LineNoisePopulation],
    Field(discriminator="kind"),
]

Coupling = Annotated[
    Union[PhaseToAmpCoupling, PhaseToPhaseCoupling],
    Field(discriminator="kind"),
]


class ProjectionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Literal["all_identical", "region_match"] = "region_match"
    channel_noise_sd: float = Field(3.0, ge=0.0)


class SignalConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    populations: list[Population] = Field(default_factory=list)
    couplings: list[Coupling] = Field(default_factory=list)
    projection: ProjectionConfig = Field(default_factory=ProjectionConfig)

    @model_validator(mode="after")
    def _validate_refs_and_acyclic(self) -> SignalConfig:
        ids = [p.id for p in self.populations]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate population ids in SignalConfig.")

        ids_set = set(ids)
        for c in self.couplings:
            if c.driver not in ids_set:
                raise ValueError(
                    f"Coupling driver {c.driver!r} not a population id."
                )
            if c.target not in ids_set:
                raise ValueError(
                    f"Coupling target {c.target!r} not a population id."
                )
            if c.driver == c.target:
                raise ValueError(
                    f"Coupling driver and target must differ: {c.driver!r}."
                )

        # Iterative DFS cycle detection (avoids recursion-limit issues).
        graph: dict[str, list[str]] = {pid: [] for pid in ids}
        for c in self.couplings:
            graph[c.driver].append(c.target)

        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {pid: WHITE for pid in ids}

        for start in ids:
            if color[start] != WHITE:
                continue
            stack: list[tuple[str, int]] = [(start, 0)]
            color[start] = GRAY
            while stack:
                node, child_idx = stack[-1]
                neighbors = graph[node]
                if child_idx < len(neighbors):
                    stack[-1] = (node, child_idx + 1)
                    v = neighbors[child_idx]
                    if color[v] == GRAY:
                        raise ValueError(
                            f"Cycle in coupling graph: {node!r} → {v!r}."
                        )
                    if color[v] == WHITE:
                        color[v] = GRAY
                        stack.append((v, 0))
                else:
                    color[node] = BLACK
                    stack.pop()

        return self
