from __future__ import annotations

from dataclasses import dataclass, field

from pac_framework.core.data_model import Session
from pac_framework.generator.config import SignalConfig


@dataclass
class SubjectState:
    """GUI workspace state for the currently-loaded subject.

    This is NOT part of the scientific API — it exists only to hold the
    editor's in-flight state between Build, Generate, Save, and Load.
    Scientific code should operate on Session and SignalConfig objects
    directly via pac_framework.generate_signals().

    Rebuilt atomically on Build/Load; treat as a single value that gets
    replaced rather than a thing that gets mutated field-by-field.

    signals_populated is False immediately after Build (zero-filled channels)
    and True after Generate Signals fills them with waveform data.
    """

    subject_name: str
    master_seed: int
    notes: str
    sfreq: float
    sessions: list[Session]
    channel_layout: list[dict]
    session_signal_configs: list[SignalConfig]
    signals_populated: bool = False
