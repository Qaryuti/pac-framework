from __future__ import annotations

import uuid

import matplotlib.axes
import numpy as np
from scipy.signal import spectrogram

from pac_framework.core.data_model import Session


class SpectrogramTrack:
    def __init__(
        self,
        nperseg: int = 256,
        noverlap: int | None = None,
        fmin: float = 0.0,
        fmax: float = 150.0,
        log_scale: bool = False,
    ) -> None:
        self.id = str(uuid.uuid4())
        self.name = "Spectrogram"
        self.nperseg = nperseg
        self.noverlap = noverlap
        self.fmin = fmin
        self.fmax = fmax
        self.log_scale = log_scale

    def render(
        self,
        ax: matplotlib.axes.Axes,
        session: Session,
        channel_idx: int,
    ) -> None:
        ch_name = session.channels.names[channel_idx]
        signal = session.channels.get_channel(ch_name)
        sfreq = session.timeline.sfreq

        nperseg = min(self.nperseg, len(signal))
        noverlap = min(self.noverlap, nperseg - 1) if self.noverlap is not None else None

        f, t, Sxx = spectrogram(signal, fs=sfreq, nperseg=nperseg, noverlap=noverlap)

        fmax = min(self.fmax, sfreq / 2.0)
        mask = (f >= self.fmin) & (f <= fmax)
        f, Sxx = f[mask], Sxx[mask, :]

        if self.log_scale:
            Sxx = np.log1p(Sxx)

        ax.pcolormesh(t, f, Sxx, cmap="viridis", shading="auto")
        ax.set_ylabel("Freq (Hz)")
