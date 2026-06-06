from __future__ import annotations

import uuid

import matplotlib.axes
from scipy.signal import butter, sosfiltfilt

from pac_framework.core.data_model import Session


class FilteredTrack:
    def __init__(self, low_hz: float, high_hz: float, order: int = 4) -> None:
        self.id = str(uuid.uuid4())
        self.low_hz = low_hz
        self.high_hz = high_hz
        self.order = order
        self.name = f"Filtered {low_hz}–{high_hz} Hz"

    def render(
        self,
        ax: matplotlib.axes.Axes,
        session: Session,
        channel_idx: int,
    ) -> None:
        ch_name = session.channels.names[channel_idx]
        signal = session.channels.get_channel(ch_name)
        sfreq = session.timeline.sfreq
        t = session.timeline.times()

        nyq = sfreq / 2.0
        sos = butter(
            self.order,
            [self.low_hz / nyq, self.high_hz / nyq],
            btype="band",
            output="sos",
        )
        filtered = sosfiltfilt(sos, signal)

        ax.plot(t, filtered, linewidth=0.8, color="darkorange")
        ax.set_ylabel(f"{self.low_hz}–{self.high_hz} Hz")
