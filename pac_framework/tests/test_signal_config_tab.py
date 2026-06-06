"""Tests for Signal Config tab logic (headless — no Qt required).

These tests exercise the data-layer logic: default population specs,
per-session independence, and state mutation after population edits.
The GUI layer itself is not tested here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pac_framework.core.data_model import Channels, Events, Session, Timeline
from pac_framework.generator.config import OscillatorPopulation, SignalConfig
from pac_framework.gui.subject_state import SubjectState


# ── helpers ────────────────────────────────────────────────────────────────


def _minimal_session(session_id: str = "session_000") -> Session:
    timeline = Timeline(sfreq=100.0, n_samples=100)
    info = pd.DataFrame({"name": ["ch_00"], "type": ["synthetic"]})
    channels = Channels(data=np.zeros((1, 100)), info=info, units="µV")
    events = Events(
        samples=np.array([], dtype=np.int64),
        labels=tuple(),
        codes=np.array([], dtype=np.int64),
        code_map={},
    )
    return Session(
        subject_id="test", session_id=session_id, task="t",
        date_recorded="2026-01-01", origin="synthetic",
        timeline=timeline, channels=channels, events=events,
        ground_truth={"generator": "test"},
    )


def _state_with_empty_configs(n_sessions: int = 2) -> SubjectState:
    sessions = [_minimal_session(f"session_{i:03d}") for i in range(n_sessions)]
    return SubjectState(
        subject_name="test", master_seed=42, notes="", sfreq=100.0,
        sessions=sessions,
        channel_layout=[],
        session_signal_configs=[SignalConfig() for _ in sessions],
    )


# ── per-session config independence ────────────────────────────────────────


def test_session_configs_start_empty():
    state = _state_with_empty_configs(2)
    for sc in state.session_signal_configs:
        assert sc.populations == []


def test_editing_session_0_does_not_affect_session_1():
    state = _state_with_empty_configs(2)

    edited = SignalConfig(
        populations=[
            OscillatorPopulation(
                id="theta", center_frequency=12.0, bandwidth=2.0,
                amplitude=50.0, region="amygdala",
            )
        ]
    )
    state.session_signal_configs[0] = edited

    assert state.session_signal_configs[0].populations[0].center_frequency == 12.0
    assert state.session_signal_configs[1].populations == []


def test_session_configs_length_matches_sessions():
    state = _state_with_empty_configs(3)
    assert len(state.session_signal_configs) == len(state.sessions) == 3


# ── SignalConfig construction ──────────────────────────────────────────────


def test_signal_config_with_two_populations():
    pops = [
        OscillatorPopulation(id="theta", center_frequency=6.0, bandwidth=2.0, amplitude=1.0, region="amygdala"),
        OscillatorPopulation(id="gamma", center_frequency=60.0, bandwidth=10.0, amplitude=0.5, region="amygdala"),
    ]
    sc = SignalConfig(populations=pops)
    assert len(sc.populations) == 2
    assert sc.populations[0].id == "theta"
    assert sc.populations[1].id == "gamma"


def test_signal_config_default_projection():
    sc = SignalConfig()
    assert sc.projection.mode == "region_match"
    assert sc.projection.channel_noise_sd == 3.0


def test_signal_config_roundtrip():
    pops = [
        OscillatorPopulation(id="theta", center_frequency=6.0, bandwidth=2.0, amplitude=1.0, region="amygdala"),
        OscillatorPopulation(id="gamma", center_frequency=60.0, bandwidth=10.0, amplitude=0.5, region="amygdala"),
    ]
    sc = SignalConfig(populations=pops)
    restored = SignalConfig.model_validate(sc.model_dump())
    assert len(restored.populations) == 2
    assert restored.populations[0].center_frequency == pops[0].center_frequency
