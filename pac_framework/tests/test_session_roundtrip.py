"""Tests for Session.save() / Session.load() HDF5 round-trip."""
from __future__ import annotations

import tempfile
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest

from pac_framework.core.data_model import Channels, Events, Session, Timeline


# ── fixtures ───────────────────────────────────────────────────────────────


def _make_timeline() -> Timeline:
    return Timeline(sfreq=100.0, n_samples=500)


def _make_channels_extended() -> Channels:
    """Channels with the full anatomical info columns."""
    info = pd.DataFrame({
        "name": ["LA_00", "LA_01", "LH_00"],
        "type": ["synthetic", "synthetic", "synthetic"],
        "shaft": ["LA", "LA", "LH"],
        "region": ["amygdala", "amygdala", "hippocampus"],
        "contact_index": [0, 1, 0],
        "position_mm": [0.0, 3.0, 0.0],
    })
    data = np.random.default_rng(42).normal(0.0, 1.0, (3, 500))
    return Channels(data=data, info=info, units="µV")


def _make_channels_minimal() -> Channels:
    """Channels with only the required name/type columns."""
    info = pd.DataFrame({"name": ["ch_00"], "type": ["synthetic"]})
    return Channels(data=np.zeros((1, 500), dtype=np.float64), info=info, units="µV")


def _make_events_nonempty() -> Events:
    return Events(
        samples=np.array([10, 50, 200, 450], dtype=np.int64),
        labels=("cue", "go", "cue", "stop"),
        codes=np.array([0, 1, 0, 2], dtype=np.int64),
        code_map={"cue": 0, "go": 1, "stop": 2},
    )


def _make_events_empty() -> Events:
    return Events(
        samples=np.array([], dtype=np.int64),
        labels=tuple(),
        codes=np.array([], dtype=np.int64),
        code_map={},
    )


def _make_session(channels: Channels, events: Events) -> Session:
    return Session(
        subject_id="test_sub",
        session_id="session_000",
        task="test_task",
        date_recorded="2026-05-18",
        origin="synthetic",
        timeline=_make_timeline(),
        channels=channels,
        events=events,
        ground_truth={"generator": "test", "params": {"key": "value"}},
        annotations={"note": "hello", "flag": True},
    )


# ── helpers ────────────────────────────────────────────────────────────────


def _roundtrip(session: Session) -> Session:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "session.h5"
        session.save(path)
        return Session.load(path)


# ── tests ──────────────────────────────────────────────────────────────────


def test_roundtrip_extended_channels():
    orig = _make_session(_make_channels_extended(), _make_events_nonempty())
    loaded = _roundtrip(orig)

    # Identity
    assert loaded.subject_id == orig.subject_id
    assert loaded.session_id == orig.session_id
    assert loaded.task == orig.task
    assert loaded.date_recorded == orig.date_recorded
    assert loaded.origin == orig.origin

    # Timeline
    assert loaded.timeline.sfreq == orig.timeline.sfreq
    assert loaded.timeline.n_samples == orig.timeline.n_samples
    assert loaded.timeline.tmin == orig.timeline.tmin

    # Channel data — bit-identical
    assert np.array_equal(loaded.channels.data, orig.channels.data)
    assert loaded.channels.units == orig.channels.units

    # Channel info — all columns survive (HDF5 restores in alphabetical order,
    # so check_like=True ignores column ordering).
    pd.testing.assert_frame_equal(
        loaded.channels.info.reset_index(drop=True),
        orig.channels.info.reset_index(drop=True),
        check_dtype=False,
        check_like=True,
    )

    # Events
    assert np.array_equal(loaded.events.samples, orig.events.samples)
    assert loaded.events.labels == orig.events.labels
    assert np.array_equal(loaded.events.codes, orig.events.codes)
    assert loaded.events.code_map == orig.events.code_map

    # Metadata
    assert loaded.ground_truth == orig.ground_truth
    assert loaded.annotations == orig.annotations


def test_roundtrip_minimal_channels():
    orig = _make_session(_make_channels_minimal(), _make_events_nonempty())
    loaded = _roundtrip(orig)
    assert np.array_equal(loaded.channels.data, orig.channels.data)
    assert list(loaded.channels.info["name"]) == list(orig.channels.info["name"])


def test_roundtrip_empty_events():
    orig = _make_session(_make_channels_extended(), _make_events_empty())
    loaded = _roundtrip(orig)
    assert loaded.events.n_events == 0
    assert loaded.events.labels == tuple()
    assert loaded.events.code_map == {}


def test_roundtrip_data_bit_identical():
    """Explicit check: loaded data array must equal original element-by-element."""
    rng = np.random.default_rng(123)
    info = pd.DataFrame({"name": ["a", "b"], "type": ["synthetic", "synthetic"]})
    channels = Channels(
        data=rng.normal(0.0, 50.0, (2, 500)), info=info, units="µV"
    )
    orig = _make_session(channels, _make_events_empty())
    loaded = _roundtrip(orig)
    assert np.array_equal(loaded.channels.data, orig.channels.data)


def test_roundtrip_ground_truth_and_annotations():
    orig = _make_session(_make_channels_minimal(), _make_events_empty())
    loaded = _roundtrip(orig)
    assert loaded.ground_truth == {"generator": "test", "params": {"key": "value"}}
    assert loaded.annotations == {"note": "hello", "flag": True}


# ── G6 ground-truth bundle round-trip ─────────────────────────────────────


def _minimal_session_gt(ground_truth: dict) -> Session:
    info = pd.DataFrame({"name": ["ch_0"], "type": ["synthetic"]})
    return Session(
        subject_id="test",
        session_id="s0",
        task="test",
        date_recorded="2026-01-01",
        origin="synthetic",
        timeline=Timeline(sfreq=100.0, n_samples=50),
        channels=Channels(data=np.zeros((1, 50)), info=info, units="µV"),
        events=Events(
            samples=np.array([], dtype=np.int64),
            labels=tuple(),
            codes=np.array([], dtype=np.int64),
            code_map={},
        ),
        ground_truth=ground_truth,
    )


def test_roundtrip_empty_ground_truth():
    """Session with ground_truth={} saves and loads as empty dict."""
    loaded = _roundtrip(_minimal_session_gt({}))
    assert loaded.ground_truth == {}


def test_roundtrip_full_ground_truth_bundle():
    """Full bundle with numpy arrays round-trips bit-identically."""
    rng = np.random.default_rng(7)
    n = 50
    bundle = {
        "pre_coupling_carriers": {
            "theta": rng.standard_normal(n),
            "gamma": rng.standard_normal(n),
        },
        "phases": {
            "theta": np.linspace(-np.pi, np.pi, n),
            "gamma": np.linspace(-np.pi, np.pi, n),
        },
        "chi_trajectories": {
            "theta__to__gamma": np.full(n, 0.5, dtype=np.float64),
        },
        "projection_matrix": rng.standard_normal((2, 4)),
        "oscillator_order": ["theta", "gamma"],
        "channel_order": ["c0", "c1", "c2", "c3"],
        "signal_config_json": '{"populations":[],"couplings":[],"projection":{"mode":"region_match","channel_noise_sd":3.0}}',
    }
    loaded = _roundtrip(_minimal_session_gt(bundle))
    gt = loaded.ground_truth

    for pid in ("theta", "gamma"):
        assert np.array_equal(gt["pre_coupling_carriers"][pid],
                              bundle["pre_coupling_carriers"][pid])
        assert np.array_equal(gt["phases"][pid], bundle["phases"][pid])

    assert np.array_equal(gt["chi_trajectories"]["theta__to__gamma"],
                          bundle["chi_trajectories"]["theta__to__gamma"])
    assert np.array_equal(gt["projection_matrix"], bundle["projection_matrix"])
    assert gt["oscillator_order"] == ["theta", "gamma"]
    assert gt["channel_order"] == ["c0", "c1", "c2", "c3"]
    assert gt["signal_config_json"] == bundle["signal_config_json"]


def test_old_file_without_ground_truth_group():
    """Synthetic session HDF5 file with no ground_truth group loads as ground_truth={}."""
    session = _minimal_session_gt({})
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "session.h5"
        session.save(path)
        # Remove the group entirely to simulate a pre-G6 file
        with h5py.File(path, "a") as f:
            del f["ground_truth"]
        loaded = Session.load(path)
    assert loaded.ground_truth == {}
    assert loaded.subject_id == session.subject_id
