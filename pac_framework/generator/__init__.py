from pac_framework.generator.background import synth_background
from pac_framework.generator.couplings import apply_phase_to_amplitude
from pac_framework.generator.line_noise import synth_line_noise
from pac_framework.generator.oscillator import OscillatorOutput, synth_oscillator
from pac_framework.generator.pipeline import apply_couplings
from pac_framework.generator.projection import build_projection_matrix
from pac_framework.generator.scheduling import schedule_class_events
from pac_framework.generator.config import (
    ArtifactConfig,
    BackgroundPopulation,
    BurstConfig,
    EventClass,
    EventModulation,
    LineNoisePopulation,
    OscillatorPopulation,
    PAFDrift,
    PhaseToAmpCoupling,
    PhaseToPhaseCoupling,
    ProjectionConfig,
    SessionSpec,
    SignalConfig,
    WaveformShape,
)
from pac_framework.generator.runner import build_sessions, channel_info_from_shafts, generate_signals

__all__ = [
    "synth_background",
    "apply_phase_to_amplitude",
    "synth_line_noise",
    "OscillatorOutput",
    "synth_oscillator",
    "apply_couplings",
    "build_projection_matrix",
    "schedule_class_events",
    # Experiment design
    "EventClass",
    "SessionSpec",
    # Signal configuration
    "ArtifactConfig",
    "BackgroundPopulation",
    "BurstConfig",
    "EventModulation",
    "LineNoisePopulation",
    "OscillatorPopulation",
    "PAFDrift",
    "PhaseToAmpCoupling",
    "PhaseToPhaseCoupling",
    "ProjectionConfig",
    "SignalConfig",
    "WaveformShape",
    # Synthesis entry points
    "channel_info_from_shafts",
    "build_sessions",
    "generate_signals",
]
