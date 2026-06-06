"""Modal dialog for advanced per-oscillator parameters.

Groups the less-used fields (WaveformShape, PAFDrift, BurstConfig, Artifacts)
behind a single "Advanced…" button so the main oscillator table stays compact.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

_DEFAULTS: dict = {
    "sharpness": 0.0,
    "asymmetry": 0.0,
    "paf_sigma": 0.0,
    "paf_tau": 5.0,
    "burst_mode": "continuous",
    "burst_rate": 0.5,
    "burst_dur_mean": 3.0,
    "burst_dur_sd": 0.5,
    "burst_refractory": 1.0,
    "artifact_rate": 0.0,
    "artifact_amp_mult": 3.0,
    "artifact_width": 5,
}


def default_advanced_params() -> dict:
    """Return a fresh copy of the default advanced parameter dict."""
    return dict(_DEFAULTS)


class OscillatorAdvancedDialog(QDialog):
    """Form dialog for waveform shape, PAF drift, burst config, and artifact params."""

    def __init__(self, params: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced Oscillator Parameters")
        self.setMinimumWidth(440)
        self._build_ui()
        self._load(params)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(self._waveform_group())
        layout.addWidget(self._paf_group())
        layout.addWidget(self._burst_group())
        layout.addWidget(self._artifact_group())
        layout.addLayout(self._button_row())

    def _waveform_group(self) -> QGroupBox:
        group = QGroupBox("Waveform Shape")
        form = QFormLayout(group)
        form.addRow(_info(
            "Injects harmonics to distort the sinusoid. Positive sharpness = sharper peaks "
            "(like hippocampal theta). Positive asymmetry = fast rise, slow decay. "
            "Both zero = pure sine. Defaults are fine for most use cases."
        ))
        self._sharpness = _double_spin(-1.0, 1.0, step=0.1, decimals=2)
        form.addRow("Peak/trough sharpness  [−1 … 1]", self._sharpness)
        self._asymmetry = _double_spin(-1.0, 1.0, step=0.1, decimals=2)
        form.addRow("Rise/decay asymmetry  [−1 … 1]", self._asymmetry)
        return group

    def _paf_group(self) -> QGroupBox:
        group = QGroupBox("Peak-Frequency (PAF) Drift")
        form = QFormLayout(group)
        form.addRow(_info(
            "Adds slow random drift to the center frequency using an Ornstein-Uhlenbeck "
            "process. σ controls how far the frequency wanders; τ controls how slowly it "
            "changes. Set σ = 0 (default) for a fixed frequency."
        ))
        self._paf_sigma = _double_spin(0.0, 20.0, step=0.1, decimals=2)
        form.addRow("σ  (Hz) — drift magnitude", self._paf_sigma)
        self._paf_tau = _double_spin(0.01, 300.0, step=1.0, decimals=2)
        form.addRow("τ  (s) — correlation time", self._paf_tau)
        return group

    def _burst_group(self) -> QGroupBox:
        group = QGroupBox("Burst Config")
        form = QFormLayout(group)
        form.addRow(_info(
            "Controls whether the oscillation fires continuously or in intermittent bursts. "
            "In bursty mode, burst onsets follow a Poisson process at the given rate; "
            "each burst lasts a random number of cycles drawn from a normal distribution "
            "and is tapered with a raised-cosine ramp to avoid hard edges. "
            "The refractory period sets the minimum gap between bursts."
        ))
        self._burst_mode = QComboBox()
        self._burst_mode.addItems(["continuous", "bursty"])
        form.addRow("Mode", self._burst_mode)
        self._burst_rate = _double_spin(0.01, 100.0, step=0.1, decimals=2)
        form.addRow("Rate  (Hz)", self._burst_rate)
        self._burst_dur_mean = _double_spin(0.01, 100.0, step=0.5, decimals=2)
        form.addRow("Duration mean  (cycles)", self._burst_dur_mean)
        self._burst_dur_sd = _double_spin(0.0, 50.0, step=0.1, decimals=2)
        form.addRow("Duration SD  (cycles)", self._burst_dur_sd)
        self._burst_refract = _double_spin(0.0, 100.0, step=0.5, decimals=2)
        form.addRow("Refractory  (cycles)", self._burst_refract)
        return group

    def _artifact_group(self) -> QGroupBox:
        group = QGroupBox("Artifacts")
        form = QFormLayout(group)
        form.addRow(_info(
            "Injects sharp transient spikes (electrode movement, saturation, etc.) "
            "at a random Poisson rate. Amplitude is a multiplier of the carrier's "
            "standard deviation. Width is in samples (e.g. 5 samples = 5 ms at 1 kHz). "
            "Set rate = 0 (default) to disable entirely."
        ))
        self._art_rate = _double_spin(0.0, 100.0, step=0.1, decimals=2)
        form.addRow("Rate  (Hz)", self._art_rate)
        self._art_amp = _double_spin(0.01, 100.0, step=0.5, decimals=2)
        form.addRow("Amplitude ×", self._art_amp)
        self._art_width = QSpinBox()
        self._art_width.setRange(1, 1000)
        form.addRow("Width  (samples)", self._art_width)
        return group

    def _button_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        return row

    # ── data in / out ─────────────────────────────────────────────────────

    def _load(self, params: dict) -> None:
        p = {**_DEFAULTS, **params}
        self._sharpness.setValue(p["sharpness"])
        self._asymmetry.setValue(p["asymmetry"])
        self._paf_sigma.setValue(p["paf_sigma"])
        self._paf_tau.setValue(p["paf_tau"])
        self._burst_mode.setCurrentText(p["burst_mode"])
        self._burst_rate.setValue(p["burst_rate"])
        self._burst_dur_mean.setValue(p["burst_dur_mean"])
        self._burst_dur_sd.setValue(p["burst_dur_sd"])
        self._burst_refract.setValue(p["burst_refractory"])
        self._art_rate.setValue(p["artifact_rate"])
        self._art_amp.setValue(p["artifact_amp_mult"])
        self._art_width.setValue(int(p["artifact_width"]))

    def get_params(self) -> dict:
        return {
            "sharpness": self._sharpness.value(),
            "asymmetry": self._asymmetry.value(),
            "paf_sigma": self._paf_sigma.value(),
            "paf_tau": self._paf_tau.value(),
            "burst_mode": self._burst_mode.currentText(),
            "burst_rate": self._burst_rate.value(),
            "burst_dur_mean": self._burst_dur_mean.value(),
            "burst_dur_sd": self._burst_dur_sd.value(),
            "burst_refractory": self._burst_refract.value(),
            "artifact_rate": self._art_rate.value(),
            "artifact_amp_mult": self._art_amp.value(),
            "artifact_width": self._art_width.value(),
        }


# ── helpers ───────────────────────────────────────────────────────────────────

def _info(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #555; font-style: italic; font-size: 8pt;")
    lbl.setContentsMargins(0, 0, 0, 4)
    return lbl


def _double_spin(lo: float, hi: float, step: float, decimals: int) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(lo, hi)
    spin.setSingleStep(step)
    spin.setDecimals(decimals)
    return spin
