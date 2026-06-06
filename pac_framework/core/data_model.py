"""Immutable data model for PAC Framework electrophysiology data.

Key objects:
    Timeline   — shared time axis (sfreq, n_samples, tmin)
    Channels   — multichannel voltage data + queryable metadata
    Events     — discrete event markers + trial metadata
    Session    — immutable container combining all of the above
    Subject    — lightweight index over sessions
    Result     — pipeline output with provenance
    SourceRef  — lightweight back-reference from Result to Session
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import h5py
import numpy as np
import pandas as pd


# ── helpers ───────────────────────────────────────────────────────────────


def _write_col(group: h5py.Group, col: str, values) -> None:
    """Numeric dataset if possible; UTF-8 bytes otherwise (string columns)."""
    arr = np.asarray(values)
    try:
        if arr.dtype.kind in ('U', 'O', 'S', 'T'):
            raise ValueError
        group.create_dataset(col, data=arr)
    except (TypeError, ValueError):
        group.create_dataset(
            col, data=np.array([str(v).encode('utf-8') for v in values])
        )


class ValidationError(Exception):
    """Raised when a data model object fails structural validation."""
    pass


def _freeze_array(arr: np.ndarray) -> np.ndarray:
    arr = np.array(arr)
    arr.flags.writeable = False
    return arr


# Keys that get their own HDF5 groups / datasets in the ground-truth bundle.
# Anything outside this set is stored as a legacy JSON attribute.
_BUNDLE_KEYS = frozenset({
    "pre_coupling_carriers", "phases", "chi_trajectories",
    "line_noise", "backgrounds",
    "projection_matrix", "oscillator_order", "channel_order",
    "signal_config_json",
})

_BUNDLE_ARRAY_GROUPS = (
    "pre_coupling_carriers", "phases", "chi_trajectories",
    "line_noise", "backgrounds",
)


# ── data objects ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Timeline:
    """Shared time axis.  t_k = tmin + k / sfreq."""
    sfreq: float
    n_samples: int
    tmin: float = 0.0

    def __post_init__(self):
        if self.sfreq <= 0:
            raise ValidationError(f"Sampling frequency must be positive, got {self.sfreq}")
        if self.n_samples <= 0:
            raise ValidationError(f"Number of samples must be positive, got {self.n_samples}")

    @property
    def duration(self) -> float:
        return self.n_samples / self.sfreq

    @property
    def tmax(self) -> float:
        return self.tmin + (self.n_samples - 1) / self.sfreq

    def sample_to_time(self, sample: int) -> float:
        return self.tmin + sample / self.sfreq

    def time_to_sample(self, time: float) -> int:
        sample = int(round((time - self.tmin) * self.sfreq))
        return max(0, min(sample, self.n_samples - 1))

    def times(self) -> np.ndarray:
        t = np.arange(self.n_samples) / self.sfreq + self.tmin
        t.flags.writeable = False
        return t


# Channels

@dataclass(frozen=True)
class Channels:
    """Multichannel voltage data with queryable metadata.

    data: (n_channels, n_samples) float64 matrix.
    info: DataFrame with columns 'name' (unique) and 'type' required;
          extra columns (region, shaft, contact_index, …) are passed through.
    """
    data: np.ndarray
    info: pd.DataFrame
    units: str

    def __post_init__(self):
        frozen = _freeze_array(self.data)
        object.__setattr__(self, 'data', frozen)

        info_copy = self.info.copy()
        info_copy.reset_index(drop=True, inplace=True)
        object.__setattr__(self, 'info', info_copy)

        if self.data.ndim != 2:
            raise ValidationError(f"Channel data must be 2D, got shape {self.data.shape}")

        n_ch = self.data.shape[0]

        if 'name' not in self.info.columns:
            raise ValidationError("Channel info must have a 'name' column")
        if 'type' not in self.info.columns:
            raise ValidationError("Channel info must have a 'type' column")
        if len(self.info) != n_ch:
            raise ValidationError(
                f"Channel info has {len(self.info)} rows but data has {n_ch} channels")

        names = self.info['name'].tolist()
        if len(set(names)) != len(names):
            dupes = [n for n in names if names.count(n) > 1]
            raise ValidationError(f"Channel names must be unique, duplicates: {set(dupes)}")

    @property
    def n_channels(self) -> int:
        return self.data.shape[0]

    @property
    def n_samples(self) -> int:
        return self.data.shape[1]

    @property
    def names(self) -> list[str]:
        return self.info['name'].tolist()

    @property
    def types(self) -> list[str]:
        return self.info['type'].tolist()

    def get_index(self, name: str) -> int:
        matches = self.info.index[self.info['name'] == name].tolist()
        if not matches:
            raise KeyError(f"Channel '{name}' not found. Available: {self.names}")
        return matches[0]

    def get_channel(self, name: str) -> np.ndarray:
        idx = self.get_index(name)
        return self.data[idx, :]

    def select(self, **kwargs) -> list[str]:
        mask = pd.Series(True, index=self.info.index)
        for col, value in kwargs.items():
            if col not in self.info.columns:
                raise KeyError(f"Column '{col}' not in channel info. Available: {self.info.columns.tolist()}")
            if isinstance(value, (list, tuple, set)):
                mask = mask & self.info[col].isin(value)
            else:
                mask = mask & (self.info[col] == value)
        return self.info.loc[mask, 'name'].tolist()

    def get_channels(self, **kwargs) -> np.ndarray:
        names = self.select(**kwargs)
        if not names:
            raise KeyError(f"No channels match criteria: {kwargs}")
        indices = [self.get_index(n) for n in names]
        return _freeze_array(self.data[indices, :])

    def get_info(self, name: str) -> dict:
        idx = self.get_index(name)
        return self.info.iloc[idx].to_dict()

    def list_unique(self, column: str) -> list:
        if column not in self.info.columns:
            raise KeyError(f"Column '{column}' not in channel info. Available: {self.info.columns.tolist()}")
        return self.info[column].dropna().unique().tolist()

    def group_by(self, column: str) -> dict[str, list[str]]:
        if column not in self.info.columns:
            raise KeyError(f"Column '{column}' not in channel info. Available: {self.info.columns.tolist()}")
        groups = {}
        for value, group_df in self.info.groupby(column):
            groups[value] = group_df['name'].tolist()
        return groups

    def summary(self) -> str:
        lines = [f"Channels: {self.n_channels} ch, {self.n_samples:,} samples, units={self.units}"]
        extra_cols = [c for c in self.info.columns if c not in ('name', 'type')]
        if extra_cols:
            lines.append(f"  Metadata: {extra_cols}")
        type_counts = self.info['type'].value_counts().to_dict()
        lines.append(f"  Types: {type_counts}")
        if 'area' in self.info.columns:
            area_counts = self.info['area'].value_counts().to_dict()
            lines.append(f"  Areas: {area_counts}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Events:
    """Discrete event markers as sample indices into the session timeline."""
    samples: np.ndarray
    labels: tuple[str, ...]
    codes: np.ndarray
    code_map: dict[str, int]
    trial_metadata: Optional[pd.DataFrame] = None

    def __post_init__(self):
        frozen_samples = _freeze_array(self.samples)
        frozen_codes = _freeze_array(self.codes)
        object.__setattr__(self, 'samples', frozen_samples)
        object.__setattr__(self, 'codes', frozen_codes)

        n_events = len(self.samples)
        if len(self.labels) != n_events:
            raise ValidationError(f"Labels count ({len(self.labels)}) != events count ({n_events})")
        if len(self.codes) != n_events:
            raise ValidationError(f"Codes count ({len(self.codes)}) != events count ({n_events})")
        if n_events > 1 and not np.all(np.diff(self.samples) >= 0):
            raise ValidationError("Event samples must be sorted ascending")
        missing = set(self.labels) - set(self.code_map.keys())
        if missing:
            raise ValidationError(f"Labels missing from code_map: {missing}")

        if self.trial_metadata is not None:
            if len(self.trial_metadata) != n_events:
                raise ValidationError(
                    f"trial_metadata has {len(self.trial_metadata)} rows but "
                    f"there are {n_events} events")

    @property
    def n_events(self) -> int:
        return len(self.samples)

    def select(self, label: str) -> tuple[np.ndarray, np.ndarray]:
        mask = np.array([l == label for l in self.labels])
        return _freeze_array(self.samples[mask]), _freeze_array(np.where(mask)[0])

    def select_multiple(self, labels: list[str]) -> tuple[np.ndarray, list[str]]:
        label_set = set(labels)
        mask = np.array([l in label_set for l in self.labels])
        return _freeze_array(self.samples[mask]), [l for l, m in zip(self.labels, mask) if m]


@dataclass(frozen=True)
class Session:
    """Immutable container for one recording session or synthetic generation."""
    subject_id: str
    session_id: str
    task: str
    date_recorded: str
    origin: str
    timeline: Timeline
    channels: Channels
    events: Events
    ground_truth: Optional[dict] = None
    annotations: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.channels.n_samples != self.timeline.n_samples:
            raise ValidationError(
                f"Channel data has {self.channels.n_samples} samples but timeline specifies {self.timeline.n_samples}")
        if self.origin not in ("real", "synthetic"):
            raise ValidationError(f"Origin must be 'real' or 'synthetic', got '{self.origin}'")
        if self.origin == "synthetic" and self.ground_truth is None:
            raise ValidationError("Synthetic sessions must have ground_truth")
        if self.origin == "real" and self.ground_truth is not None:
            raise ValidationError("Real sessions must not have ground_truth")
        if self.events.n_events > 0:
            if self.events.samples.max() >= self.timeline.n_samples:
                raise ValidationError(f"Event sample {self.events.samples.max()} exceeds n_samples")
            if self.events.samples.min() < 0:
                raise ValidationError(f"Negative event sample index")

    def get_channel(self, name: str) -> np.ndarray:
        return self.channels.get_channel(name)

    def select_channels(self, **kwargs) -> list[str]:
        return self.channels.select(**kwargs)

    def get_channels(self, **kwargs) -> np.ndarray:
        return self.channels.get_channels(**kwargs)

    @property
    def duration(self) -> float:
        return self.timeline.duration

    def summary(self) -> str:
        lines = [
            f"Session({self.subject_id}/{self.session_id})",
            f"  Task: {self.task}  |  Origin: {self.origin}  |  Date: {self.date_recorded}",
            f"  Duration: {self.duration:.1f}s  |  Sfreq: {self.timeline.sfreq:.0f} Hz  |  Events: {self.events.n_events}",
            f"  {self.channels.summary()}",
        ]
        if self.ground_truth is not None:
            lines.append(f"  Ground truth keys: {list(self.ground_truth.keys())}")
        return "\n".join(lines)

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with h5py.File(path, 'w') as f:
            ident = f.create_group('identity')
            ident.attrs['subject_id'] = self.subject_id
            ident.attrs['session_id'] = self.session_id
            ident.attrs['task'] = self.task
            ident.attrs['date_recorded'] = self.date_recorded
            ident.attrs['origin'] = self.origin

            tl = f.create_group('timeline')
            tl.attrs['sfreq'] = self.timeline.sfreq
            tl.attrs['n_samples'] = self.timeline.n_samples
            tl.attrs['tmin'] = self.timeline.tmin

            ch = f.create_group('channels')
            ch.create_dataset('data', data=self.channels.data,
                              compression='gzip', compression_opts=4)
            ch.attrs['units'] = self.channels.units
            ch_info = ch.create_group('info')
            for col in self.channels.info.columns:
                _write_col(ch_info, col, self.channels.info[col].values)

            ev = f.create_group('events')
            ev.create_dataset('samples', data=self.events.samples)
            ev.create_dataset('labels',
                              data=np.array([l.encode('utf-8') for l in self.events.labels]))
            ev.create_dataset('codes', data=self.events.codes)
            ev.attrs['code_map'] = json.dumps(self.events.code_map)
            if self.events.trial_metadata is not None:
                tm = ev.create_group('trial_metadata')
                for col in self.events.trial_metadata.columns:
                    _write_col(tm, col, self.events.trial_metadata[col].values)

            gt = f.create_group('ground_truth')
            if self.ground_truth:
                # Per-population array sub-groups (gzip-compressed)
                for sub_key in _BUNDLE_ARRAY_GROUPS:
                    if sub_key in self.ground_truth:
                        sub = gt.create_group(sub_key)
                        for name, arr in self.ground_truth[sub_key].items():
                            sub.create_dataset(
                                name,
                                data=np.asarray(arr, dtype=np.float64),
                                compression='gzip', compression_opts=4,
                            )
                if 'projection_matrix' in self.ground_truth:
                    gt.create_dataset(
                        'projection_matrix',
                        data=np.asarray(self.ground_truth['projection_matrix'], dtype=np.float64),
                        compression='gzip', compression_opts=4,
                    )
                for attr_key in ('oscillator_order', 'channel_order'):
                    if attr_key in self.ground_truth:
                        gt.attrs[attr_key] = json.dumps(self.ground_truth[attr_key])
                if 'signal_config_json' in self.ground_truth:
                    gt.attrs['signal_config_json'] = str(
                        self.ground_truth['signal_config_json']
                    )
                # Anything outside the known bundle keys goes in a JSON attribute
                # (e.g. the legacy "generator" placeholder from skeleton sessions).
                legacy = {k: v for k, v in self.ground_truth.items()
                          if k not in _BUNDLE_KEYS}
                if legacy:
                    gt.attrs['data'] = json.dumps(legacy)

            ann = f.create_group('annotations')
            if self.annotations:
                ann.attrs['data'] = json.dumps(self.annotations)

    @classmethod
    def load(cls, path: str | Path) -> Session:
        path = Path(path)
        with h5py.File(path, 'r') as f:
            ident = f['identity']
            tl_grp = f['timeline']
            timeline = Timeline(
                sfreq=float(tl_grp.attrs['sfreq']),
                n_samples=int(tl_grp.attrs['n_samples']),
                tmin=float(tl_grp.attrs['tmin']))

            ch = f['channels']
            info_dict = {}
            for col in ch['info']:
                values = ch['info'][col][:]
                if values.dtype.kind == 'S':
                    values = np.array([v.decode('utf-8') for v in values])
                info_dict[col] = values
            channels = Channels(
                data=ch['data'][:], info=pd.DataFrame(info_dict),
                units=ch.attrs['units'])

            ev = f['events']
            ev_labels = tuple(
                v.decode('utf-8') if isinstance(v, bytes) else v
                for v in ev['labels'][:])
            trial_metadata = None
            if 'trial_metadata' in ev:
                tm_data = {}
                for col in ev['trial_metadata']:
                    values = ev['trial_metadata'][col][:]
                    if values.dtype.kind == 'S':
                        values = np.array([v.decode('utf-8') for v in values])
                    tm_data[col] = values
                trial_metadata = pd.DataFrame(tm_data)
            events = Events(
                samples=ev['samples'][:], labels=ev_labels,
                codes=ev['codes'][:],
                code_map=json.loads(ev.attrs['code_map']),
                trial_metadata=trial_metadata)

            # Read origin early so we can choose the correct ground_truth default.
            origin_val = ident.attrs['origin']

            # origin determines whether ground_truth starts as {} or None
            origin_val = ident.attrs['origin']
            ground_truth: Optional[dict] = {} if origin_val == 'synthetic' else None
            if 'ground_truth' in f:
                gt = f['ground_truth']
                if 'data' in gt.attrs:
                    try:
                        parsed = json.loads(gt.attrs['data'])
                        if isinstance(parsed, dict):
                            if ground_truth is None:
                                ground_truth = {}
                            ground_truth.update(parsed)
                    except Exception:
                        pass
                for sub_key in _BUNDLE_ARRAY_GROUPS:
                    if sub_key in gt:
                        if ground_truth is None:
                            ground_truth = {}
                        ground_truth[sub_key] = {
                            name: gt[sub_key][name][:]
                            for name in gt[sub_key]
                        }
                if 'projection_matrix' in gt:
                    if ground_truth is None:
                        ground_truth = {}
                    ground_truth['projection_matrix'] = gt['projection_matrix'][:]
                for attr_key in ('oscillator_order', 'channel_order'):
                    if attr_key in gt.attrs:
                        try:
                            if ground_truth is None:
                                ground_truth = {}
                            ground_truth[attr_key] = json.loads(gt.attrs[attr_key])
                        except Exception:
                            pass
                if 'signal_config_json' in gt.attrs:
                    if ground_truth is None:
                        ground_truth = {}
                    ground_truth['signal_config_json'] = str(gt.attrs['signal_config_json'])

            annotations = {}
            if 'data' in f['annotations'].attrs:
                annotations = json.loads(f['annotations'].attrs['data'])

            subject_id = ident.attrs['subject_id']
            session_id = ident.attrs['session_id']
            task_val = ident.attrs['task']
            date_val = ident.attrs['date_recorded']

        return cls(
            subject_id=subject_id, session_id=session_id,
            task=task_val, date_recorded=date_val, origin=origin_val,
            timeline=timeline, channels=channels, events=events,
            ground_truth=ground_truth, annotations=annotations)

    def compute_hash(self) -> str:
        h = hashlib.sha256()
        h.update(self.channels.data.tobytes())
        h.update(self.events.samples.tobytes())
        h.update(self.events.codes.tobytes())
        h.update(str(self.timeline.sfreq).encode())
        h.update(str(self.timeline.n_samples).encode())
        h.update(self.subject_id.encode())
        h.update(self.session_id.encode())
        return h.hexdigest()


@dataclass(frozen=True)
class SourceRef:
    subject_id: str
    session_id: str
    channel: Optional[str]
    source_hash: str

    @classmethod
    def from_session(cls, session: Session, channel: Optional[str] = None) -> SourceRef:
        return cls(subject_id=session.subject_id, session_id=session.session_id,
                   channel=channel, source_hash=session.compute_hash())


@dataclass(frozen=True)
class Result:
    values: dict[str, Any]
    source_ref: SourceRef
    provenance: tuple[dict, ...]
    pipeline_config: dict
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        serializable_values = {}
        for k, v in self.values.items():
            if isinstance(v, np.ndarray):
                serializable_values[k] = {"__ndarray__": True,
                                          "data": v.tolist(),
                                          "dtype": str(v.dtype)}
            else:
                serializable_values[k] = v
        data = {
            "values": serializable_values,
            "source_ref": {"subject_id": self.source_ref.subject_id,
                           "session_id": self.source_ref.session_id,
                           "channel": self.source_ref.channel,
                           "source_hash": self.source_ref.source_hash},
            "provenance": list(self.provenance),
            "pipeline_config": self.pipeline_config,
            "created_at": self.created_at}
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

    @classmethod
    def load(cls, path: str | Path) -> Result:
        with open(path, 'r') as f:
            data = json.load(f)
        values = {}
        for k, v in data["values"].items():
            if isinstance(v, dict) and v.get("__ndarray__"):
                values[k] = np.array(v["data"], dtype=v["dtype"])
            else:
                values[k] = v
        return cls(values=values, source_ref=SourceRef(**data["source_ref"]),
                   provenance=tuple(data["provenance"]),
                   pipeline_config=data["pipeline_config"], created_at=data["created_at"])


@dataclass(frozen=True)
class SessionRef:
    session_id: str
    task: str
    date_recorded: str
    origin: str
    n_channels: int
    duration_sec: float
    source_path: str


@dataclass
class Subject:
    subject_id: str
    demographics: Optional[dict] = None
    session_registry: dict[str, SessionRef] = field(default_factory=dict)

    def add_session_ref(self, ref: SessionRef) -> None:
        self.session_registry[ref.session_id] = ref

    def list_sessions(self) -> list[str]:
        return list(self.session_registry.keys())

    def load_session(self, session_id: str) -> Session:
        if session_id not in self.session_registry:
            raise KeyError(f"Session '{session_id}' not found. Available: {self.list_sessions()}")
        return Session.load(self.session_registry[session_id].source_path)

    @classmethod
    def from_manifest(cls, manifest: list[dict], subject_id: str) -> Subject:
        subject = cls(subject_id=subject_id)
        for entry in manifest:
            if entry.get("subject_id") == subject_id:
                subject.add_session_ref(SessionRef(
                    session_id=entry["session_id"],
                    task=entry.get("task", "unknown"),
                    date_recorded=entry.get("date_recorded", "unknown"),
                    origin=entry.get("origin", "real"),
                    n_channels=entry.get("n_channels", 0),
                    duration_sec=entry.get("duration_sec", 0.0),
                    source_path=entry["source_path"]))
        return subject