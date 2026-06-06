from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import QWidget

from pac_framework.core.data_model import Session

_EVENT_COLORS = ["tomato", "steelblue", "forestgreen", "gold", "gray"]


class TimelinePreview(QWidget):
    """Compact read-only view of scheduled event times for one session.

    Shows vertical tick marks on a horizontal time axis, color-coded by
    event class. Displays a placeholder when no events are available yet.
    Call set_session() to update; triggers an immediate repaint.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: Session | None = None

    def set_session(self, session: Session | None) -> None:
        self._session = session
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        rect = self.rect()
        w, h = rect.width(), rect.height()

        painter.fillRect(rect, QColor("#f5f5f5"))

        has_events = (
            self._session is not None
            and self._session.events.n_events > 0
        )

        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        fm = painter.fontMetrics()

        if not has_events:
            painter.setPen(QColor("#999999"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Build to preview events")
            painter.end()
            return

        session = self._session
        duration = session.timeline.duration
        event_times = session.events.samples / session.timeline.sfreq
        codes = session.events.codes

        # Collect unique (code → label) for the legend
        seen: dict[int, str] = {}
        for label, code in zip(session.events.labels, codes):
            if int(code) not in seen:
                seen[int(code)] = label

        # Dynamic right margin to fit legend text
        max_label_w = max(
            (fm.horizontalAdvance(v[:14]) for v in seen.values()),
            default=0,
        )
        margin_left = 28
        margin_bottom = 18
        margin_top = 6
        margin_right = max(max_label_w + 22, 70)  # 12px square + gap + text

        plot_w = w - margin_left - margin_right
        axis_y = h - margin_bottom

        if plot_w <= 0:
            painter.end()
            return

        # Axis line
        painter.setPen(QColor("#cccccc"))
        painter.drawLine(margin_left, axis_y, margin_left + plot_w, axis_y)

        # Time labels
        font_small = QFont()
        font_small.setPointSize(8)
        painter.setFont(font_small)
        fm_small = painter.fontMetrics()
        painter.setPen(QColor("#666666"))
        painter.drawText(margin_left, h - 3, "0")
        dur_str = f"{duration:.0f}s"
        tw = fm_small.horizontalAdvance(dur_str)
        painter.drawText(margin_left + plot_w - tw, h - 3, dur_str)

        # Event ticks
        for et, code in zip(event_times, codes):
            x = margin_left + int(et / duration * plot_w)
            color = _EVENT_COLORS[min(int(code), len(_EVENT_COLORS) - 1)]
            painter.setPen(QColor(color))
            painter.drawLine(x, margin_top, x, axis_y - 1)

        # Legend
        legend_x = w - margin_right + 4
        row_h = fm_small.height() + 3
        for i, (code, label) in enumerate(sorted(seen.items())):
            y = margin_top + i * row_h
            if y + row_h > axis_y:
                break
            color = _EVENT_COLORS[min(code, len(_EVENT_COLORS) - 1)]
            painter.fillRect(legend_x, y + 2, 10, 10, QColor(color))
            painter.setPen(QColor("#333333"))
            painter.drawText(legend_x + 14, y + fm_small.height() - 1, label[:14])

        painter.end()
