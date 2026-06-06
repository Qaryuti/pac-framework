"""Save/load SubjectState to/from a subject directory (HDF5 + manifest.json)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from pac_framework.core.data_model import Subject
from pac_framework.core.manifest_migrations import (
    CURRENT_VERSION,
    load_manifest_with_migrations,
)
from pac_framework.generator.config import SignalConfig
from pac_framework.gui.subject_state import SubjectState

logger = logging.getLogger(__name__)


def save_subject(
    state: SubjectState,
    subject_dir: Path,
    supplementary: dict,
) -> Path:
    """Write one HDF5 file per session and a manifest.json into subject_dir."""
    subject_dir = Path(subject_dir)
    subject_dir.mkdir(parents=True, exist_ok=True)

    session_entries: list[dict] = []
    for session in state.sessions:
        h5_path = subject_dir / f"{session.session_id}.h5"
        session.save(h5_path)
        session_entries.append({
            "subject_id": session.subject_id,
            "session_id": session.session_id,
            "task": session.task,
            "date_recorded": session.date_recorded,
            "origin": session.origin,
            "n_channels": session.channels.n_channels,
            "duration_sec": session.timeline.duration,
            "source_path": str(h5_path.resolve()),
        })

    manifest = {
        "schema_version": CURRENT_VERSION,
        "subject_id": state.subject_name,
        "gui_config": {
            "name": state.subject_name,
            "seed": state.master_seed,
            "notes": state.notes,
            "sfreq": state.sfreq,
            "sessions": supplementary.get("sessions", []),
            "signal": supplementary.get("signal", {}),
            "channel_layout": supplementary.get("channel_layout", []),
            "signals_populated": state.signals_populated,
            "session_signal_configs": [
                sc.model_dump() for sc in state.session_signal_configs
            ],
        },
        "sessions": session_entries,
    }

    manifest_path = subject_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest_path


def load_subject(subject_dir: Path) -> tuple[SubjectState, dict]:
    """Load a SubjectState from disk, running schema migrations if needed."""
    subject_dir = Path(subject_dir)
    manifest_path = subject_dir / "manifest.json"
    with open(manifest_path) as f:
        raw = json.load(f)

    manifest = load_manifest_with_migrations(raw)

    subject = Subject.from_manifest(manifest["sessions"], manifest["subject_id"])
    sessions = [subject.load_session(sid) for sid in subject.list_sessions()]

    cfg = manifest.get("gui_config", {})

    raw_configs = cfg.get("session_signal_configs", [])
    session_signal_configs: list[SignalConfig] = []
    for i, sc_data in enumerate(raw_configs):
        try:
            session_signal_configs.append(SignalConfig.model_validate(sc_data))
        except Exception as e:
            logger.warning(
                "Failed to parse session_signal_configs[%d]: %s — using empty", i, e
            )
            session_signal_configs.append(SignalConfig())

    while len(session_signal_configs) < len(sessions):
        session_signal_configs.append(SignalConfig())

    state = SubjectState(
        subject_name=cfg.get("name", manifest.get("subject_id", "subject_001")),
        master_seed=int(cfg.get("seed", 42)),
        notes=cfg.get("notes", ""),
        sfreq=float(cfg.get("sfreq", 1000)),
        sessions=sessions,
        channel_layout=cfg.get("channel_layout", []),
        session_signal_configs=session_signal_configs,
        signals_populated=bool(cfg.get("signals_populated", False)),
    )

    supplementary = {
        "sessions": cfg.get("sessions", []),
        "channel_layout": cfg.get("channel_layout", []),
        "signal": cfg.get("signal", {}),
    }

    return state, supplementary
