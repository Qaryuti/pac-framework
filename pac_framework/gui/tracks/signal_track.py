from __future__ import annotations

import uuid

import matplotlib.axes

from pac_framework.core.data_model import Session

_EVENT_COLORS = ["tomato", "steelblue", "forestgreen", "gold", "gray"]


class SignalTrack:
    def __init__(self) -> None:
        self.id = str(uuid.uuid4())
        self.name = "Signal"

    def render(
        self,
        ax: matplotlib.axes.Axes,
        session: Session,
        channel_idx: int,
    ) -> None:
        ch_name = session.channels.names[channel_idx]
        signal = session.channels.get_channel(ch_name)
        t = session.timeline.times()
        event_times = session.events.samples / session.timeline.sfreq

        ax.plot(t, signal, linewidth=0.8, color="steelblue")
        for et, code in zip(event_times, session.events.codes):
            color = _EVENT_COLORS[min(int(code), len(_EVENT_COLORS) - 1)]
            ax.axvline(et, alpha=0.4, color=color, linewidth=0.8)
        ax.set_ylabel("Amplitude")
