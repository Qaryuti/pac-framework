"""PAC Framework — synthetic iEEG generator with phase-amplitude coupling.

Typical usage without the GUI::

    import pac_framework as pac
    import pandas as pd

    # 1. Describe the electrode layout
    channel_info = pac.channel_info_from_shafts([
        {"shaft": "LA", "region": "amygdala", "contacts": 8, "spacing_mm": 1.5},
        {"shaft": "LH", "region": "hippocampus", "contacts": 8, "spacing_mm": 1.5},
    ])

    # 2. Describe the recording sessions
    specs = [
        pac.SessionSpec(
            date="2026-01-01",
            duration_sec=120.0,
            task="visual_memory",
            event_catalog=(
                pac.EventClass("cue_onset", rate_hz=0.5, min_gap_sec=2.0),
                pac.EventClass("response",  rate_hz=0.4, min_gap_sec=1.5),
            ),
        ),
    ]

    # 3. Build skeleton sessions (zero-filled channels + scheduled events)
    sessions = pac.build_sessions(
        subject_name="sub-01",
        seed=42,
        sfreq=1000.0,
        session_specs=specs,
        channel_info=channel_info,
    )

    # 4. Configure the signal model
    theta = pac.OscillatorPopulation(
        id="theta", center_frequency=6.0, bandwidth=2.0,
        amplitude=50.0, region="hippocampus",
    )
    gamma = pac.OscillatorPopulation(
        id="gamma", center_frequency=70.0, bandwidth=10.0,
        amplitude=10.0, region="hippocampus",
        burst=pac.BurstConfig(mode="bursty", rate_hz=1.5),
    )
    config = pac.SignalConfig(
        populations=[theta, gamma],
        couplings=[
            pac.PhaseToAmpCoupling(driver="theta", target="gamma", chi=0.6, kappa=3.0),
        ],
    )

    # 5. Synthesise
    sessions = pac.generate_signals(
        sessions=sessions,
        signal_configs=[config],
        master_seed=42,
        subject_name="sub-01",
    )

    # 6. Access data
    raw = sessions[0].channels.data          # (n_channels, n_samples) ndarray
    events = sessions[0].events              # Events object
    gt = sessions[0].ground_truth            # dict with pre_coupling_carriers, phases, …
"""
from __future__ import annotations

from pac_framework._version import __version__

# ── Core data model ───────────────────────────────────────────────────────────
from pac_framework.core.data_model import (
    Channels,
    Events,
    Result,
    Session,
    Subject,
    Timeline,
)
from pac_framework.core.seed_util import derive

# ── Signal configuration ──────────────────────────────────────────────────────
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

# ── Synthesis entry points ────────────────────────────────────────────────────
from pac_framework.generator.runner import build_sessions, channel_info_from_shafts, generate_signals

__all__ = [
    # Data model
    "Session",
    "Channels",
    "Events",
    "Timeline",
    "Subject",
    "Result",
    "derive",
    # Experiment design
    "EventClass",
    "SessionSpec",
    # Signal configuration
    "SignalConfig",
    "OscillatorPopulation",
    "BackgroundPopulation",
    "LineNoisePopulation",
    "PhaseToAmpCoupling",
    "PhaseToPhaseCoupling",
    "ProjectionConfig",
    "WaveformShape",
    "BurstConfig",
    "PAFDrift",
    "ArtifactConfig",
    "EventModulation",
    # Synthesis
    "channel_info_from_shafts",
    "build_sessions",
    "generate_signals",
    # Package metadata
    "__version__",
]
