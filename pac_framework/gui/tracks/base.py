from __future__ import annotations

from typing import Protocol, runtime_checkable

import matplotlib.axes

from pac_framework.core.data_model import Session


@runtime_checkable
class Track(Protocol):
    """Anything that can render itself onto a matplotlib Axes for one session+channel."""

    id: str
    name: str

    def render(
        self,
        ax: matplotlib.axes.Axes,
        session: Session,
        channel_idx: int,
    ) -> None:
        """Draw into ax. Must set ax.set_ylabel. Must not touch x-limits."""
        ...
