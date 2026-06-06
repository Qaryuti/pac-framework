"""Qt-free entry points: build_sessions and generate_signals.

See examples/quickstart.py for end-to-end usage.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pac_framework.core.data_model import Channels, Events, Session, Timeline
from pac_framework.core.seed_util import derive
from pac_framework.generator.background import synth_background
from pac_framework.generator.config import (
    PhaseToAmpCoupling,
    SessionSpec,
    SignalConfig,
)
from pac_framework.generator.couplings import build_window_envelope
from pac_framework.generator.line_noise import synth_line_noise
from pac_framework.generator.oscillator import OscillatorOutput, synth_oscillator
from pac_framework.generator.pipeline import apply_couplings
from pac_framework.generator.projection import build_projection_matrix
from pac_framework.generator.scheduling import schedule_class_events


def channel_info_from_shafts(shaft_specs: list[dict]) -> pd.DataFrame:
    """Build a Channels.info DataFrame from shaft spec dicts.

    Each dict must have: shaft (str), region (str), contacts (int), spacing_mm (float).
    Channel names are ``{shaft}_{contact_index:02d}``.
    position_mm is the linear electrode geometry: contact_index * spacing_mm.
    """
    records: list[dict] = []
    for spec in shaft_specs:
        shaft = spec["shaft"]
        region = spec["region"]
        contacts = int(spec["contacts"])
        spacing = float(spec["spacing_mm"])
        for ci in range(contacts):
            records.append({
                "name": f"{shaft}_{ci:02d}",
                "type": "synthetic",
                "shaft": shaft,
                "region": region,
                "contact_index": ci,
                "position_mm": float(ci * spacing),
            })
    return pd.DataFrame(records)


def build_sessions(
    subject_name: str,
    seed: int,
    sfreq: float,
    session_specs: list[SessionSpec],
    channel_info: pd.DataFrame,
) -> list[Session]:
    """Build skeleton Sessions with zero-filled channels and scheduled events."""
    n_channels = len(channel_info)
    subject_seed = derive(seed, "subject", subject_name)
    sessions: list[Session] = []

    for i, spec in enumerate(session_specs):
        n_samples = int(spec.duration_sec * sfreq)
        session_seed = derive(subject_seed, "session", i)
        timeline = Timeline(sfreq=sfreq, n_samples=n_samples)

        code_map = {ec.name: idx for idx, ec in enumerate(spec.event_catalog)}
        all_times: list[float] = []
        all_labels: list[str] = []
        all_codes: list[int] = []

        for ec in spec.event_catalog:
            class_seed = derive(session_seed, "events", ec.name)
            rng = np.random.default_rng(class_seed)
            onsets = schedule_class_events(ec.rate_hz, ec.min_gap_sec, spec.duration_sec, rng)
            code = code_map[ec.name]
            for t in onsets:
                all_times.append(t)
                all_labels.append(ec.name)
                all_codes.append(code)

        if all_times:
            order = np.argsort(all_times, kind="stable")
            all_times = [all_times[k] for k in order]
            all_labels = [all_labels[k] for k in order]
            all_codes = [all_codes[k] for k in order]

        events = Events(
            samples=np.array([timeline.time_to_sample(t) for t in all_times], dtype=np.int64),
            labels=tuple(all_labels),
            codes=np.array(all_codes, dtype=np.int64),
            code_map=code_map,
        )
        channels = Channels(
            data=np.zeros((n_channels, n_samples), dtype=np.float64),
            info=channel_info,
            units="µV",
        )
        sessions.append(Session(
            subject_id=subject_name,
            session_id=f"session_{i:03d}",
            task=spec.task,
            date_recorded=spec.date,
            origin="synthetic",
            timeline=timeline,
            channels=channels,
            events=events,
            ground_truth={"generator": "sine_placeholder"},
        ))

    return sessions


def generate_signals(
    sessions: list[Session],
    signal_configs: list[SignalConfig],
    master_seed: int,
    subject_name: str,
) -> list[Session]:
    """Run the full synthesis pipeline, returning new Sessions with waveform data.

    signal_configs is matched 1:1 to sessions; trailing sessions with no
    corresponding config get an empty SignalConfig (silence + noise only).
    """
    subject_seed = derive(master_seed, "subject", subject_name)
    new_sessions: list[Session] = []

    for i, session in enumerate(sessions):
        session_seed = derive(subject_seed, "session", i)
        n_samples = session.timeline.n_samples
        sfreq = session.timeline.sfreq
        n_channels = session.channels.n_channels

        sc = signal_configs[i] if i < len(signal_configs) else SignalConfig()
        noise_sigma = sc.projection.channel_noise_sd
        oscillators = [p for p in sc.populations if p.kind == "oscillator"]
        line_noises = [p for p in sc.populations if p.kind == "line_noise"]
        backgrounds = [p for p in sc.populations if p.kind == "background_1f"]
        channels_info = session.channels.info

        # ── Oscillators → coupling → projection ───────────────────────
        osc_outputs: dict[str, OscillatorOutput] = {}
        if oscillators:
            for pop in oscillators:
                pop_seed = derive(session_seed, "population", pop.id)
                osc_outputs[pop.id] = synth_oscillator(pop, n_samples, sfreq, pop_seed)

            chi_traj: dict[str, np.ndarray] = {}
            for c in sc.couplings:
                if not isinstance(c, PhaseToAmpCoupling):
                    continue
                key = f"{c.driver}__to__{c.target}"
                if not c.event_modulations:
                    chi_traj[key] = np.full(n_samples, c.chi, dtype=np.float64)
                    continue
                lift_arrays: list[np.ndarray] = []
                for mod in c.event_modulations:
                    if mod.event_label not in session.events.code_map:
                        raise ValueError(
                            f"Coupling '{c.driver}→{c.target}' references event label "
                            f"'{mod.event_label}' which is not in the session catalog."
                        )
                    onset_samps, _ = session.events.select(mod.event_label)
                    env = build_window_envelope(
                        onset_samps, mod.window_sec, mod.latency_sec,
                        mod.edge_fraction, n_samples, sfreq,
                    )
                    lift_arrays.append((mod.peak_chi - c.chi) * env)
                max_lift = np.maximum.reduce(lift_arrays)
                chi_traj[key] = np.clip(c.chi + max_lift, 0.0, 1.0)

            final_carriers = apply_couplings(osc_outputs, sc.couplings, chi_traj)
            X = np.stack([final_carriers[pop.id] for pop in oscillators])
        else:
            chi_traj = {}
            X = np.zeros((0, n_samples), dtype=np.float64)

        M = build_projection_matrix(oscillators, channels_info, sc.projection.mode)
        channel_signals = M.T @ X

        # ── Line noise (apparatus-level; identical across channels) ───
        ln_traces: dict[str, np.ndarray] = {}
        for ln_pop in line_noises:
            ln_traces[ln_pop.id] = synth_line_noise(ln_pop, n_samples, sfreq)
        if ln_traces:
            ln_sum = np.sum(list(ln_traces.values()), axis=0)
            channel_signals = channel_signals + ln_sum[None, :]

        # ── 1/f backgrounds (identical across channels) ────────────────
        bg_traces: dict[str, np.ndarray] = {}
        for bg_pop in backgrounds:
            bg_seed = derive(session_seed, "population", bg_pop.id)
            bg_traces[bg_pop.id] = synth_background(bg_pop, n_samples, sfreq, bg_seed)
        if bg_traces:
            bg_sum = np.sum(list(bg_traces.values()), axis=0)
            channel_signals = channel_signals + bg_sum[None, :]

        # ── Per-channel independent Gaussian noise ─────────────────────
        new_data = np.empty((n_channels, n_samples), dtype=np.float64)
        for j in range(n_channels):
            channel_seed = derive(session_seed, "channel", j)
            rng = np.random.default_rng(channel_seed)
            new_data[j] = channel_signals[j] + rng.normal(0.0, noise_sigma, n_samples)

        ground_truth = {
            "pre_coupling_carriers": {
                pop.id: osc_outputs[pop.id].carrier for pop in oscillators
            },
            "phases": {
                pop.id: osc_outputs[pop.id].phase for pop in oscillators
            },
            "chi_trajectories": chi_traj,
            "line_noise": ln_traces,
            "backgrounds": bg_traces,
            "projection_matrix": M.astype(np.float64),
            "oscillator_order": [pop.id for pop in oscillators],
            "channel_order": list(channels_info["name"]),
            "signal_config_json": sc.model_dump_json(),
        }

        new_channels = Channels(
            data=new_data,
            info=session.channels.info,
            units=session.channels.units,
        )
        new_sessions.append(Session(
            subject_id=session.subject_id,
            session_id=session.session_id,
            task=session.task,
            date_recorded=session.date_recorded,
            origin=session.origin,
            timeline=session.timeline,
            channels=new_channels,
            events=session.events,
            ground_truth=ground_truth,
            annotations=dict(session.annotations),
        ))

    return new_sessions
