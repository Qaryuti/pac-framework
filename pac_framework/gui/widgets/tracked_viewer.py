from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pac_framework.core.data_model import Session
from pac_framework.gui.tracks import FilteredTrack, SignalTrack, SpectrogramTrack
from pac_framework.gui.tracks.base import Track


class TrackedViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sessions: list[Session] = []
        self._tracks: list[Track] = [SignalTrack()]
        self._setup_ui()
        self._rebuild_track_bar()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Session / channel selectors
        sel = QHBoxLayout()
        sel.addWidget(QLabel("Session:"))
        self._session_combo = QComboBox()
        self._session_combo.setEnabled(False)
        sel.addWidget(self._session_combo)
        sel.addWidget(QLabel("Channel:"))
        self._channel_combo = QComboBox()
        self._channel_combo.setEnabled(False)
        sel.addWidget(self._channel_combo)
        sel.addStretch()
        layout.addLayout(sel)

        # Track management bar (buttons rebuilt dynamically)
        self._track_bar = QWidget()
        bar_layout = QHBoxLayout(self._track_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(4)
        layout.addWidget(self._track_bar)

        # Matplotlib canvas
        self._figure = Figure()
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas, stretch=1)

        # Info strip
        self._info_label = QLabel("No subject loaded")
        layout.addWidget(self._info_label)

        self._session_combo.currentIndexChanged.connect(self._on_session_changed)
        self._channel_combo.currentIndexChanged.connect(lambda _: self._rebuild())

    # ------------------------------------------------------------------ #
    # Public interface                                                      #
    # ------------------------------------------------------------------ #

    def populate(self, sessions: list[Session]) -> None:
        self._sessions = sessions

        prev_session = self._session_combo.currentIndex()
        prev_channel = self._channel_combo.currentText()

        self._session_combo.blockSignals(True)
        self._channel_combo.blockSignals(True)

        self._session_combo.clear()
        for i in range(len(sessions)):
            self._session_combo.addItem(f"Session {i + 1}")
        self._session_combo.setEnabled(True)

        s_idx = prev_session if 0 <= prev_session < len(sessions) else 0
        self._session_combo.setCurrentIndex(s_idx)

        self._populate_channels(sessions[s_idx])
        self._channel_combo.setEnabled(True)

        c_idx = self._channel_combo.findText(prev_channel)
        self._channel_combo.setCurrentIndex(c_idx if c_idx >= 0 else 0)

        self._session_combo.blockSignals(False)
        self._channel_combo.blockSignals(False)

        self._rebuild()

    def tracks(self) -> list[Track]:
        return list(self._tracks)

    # ------------------------------------------------------------------ #
    # Track management                                                      #
    # ------------------------------------------------------------------ #

    def _add_track(self, track: Track) -> None:
        self._tracks.append(track)
        self._rebuild_track_bar()
        self._rebuild()

    def _remove_track(self, tid: str) -> None:
        self._tracks = [t for t in self._tracks if t.id != tid]
        self._rebuild_track_bar()
        self._rebuild()

    def _move_track(self, from_idx: int, to_idx: int) -> None:
        track = self._tracks.pop(from_idx)
        self._tracks.insert(to_idx, track)
        self._rebuild_track_bar()
        self._rebuild()

    def _rebuild_track_bar(self) -> None:
        bar_layout = self._track_bar.layout()
        while bar_layout.count():
            item = bar_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        n = len(self._tracks)
        for i, track in enumerate(self._tracks):
            btn = QPushButton(track.name)
            menu = QMenu(self)  # parent to self so button deletion can't affect a live menu
            menu.addAction(
                "Remove",
                lambda *_, tid=track.id: QTimer.singleShot(0, lambda: self._remove_track(tid)),
            )
            if i > 0:
                menu.addAction(
                    "Move up",
                    lambda *_, fi=i: QTimer.singleShot(0, lambda: self._move_track(fi, fi - 1)),
                )
            if i < n - 1:
                menu.addAction(
                    "Move down",
                    lambda *_, fi=i: QTimer.singleShot(0, lambda: self._move_track(fi, fi + 1)),
                )
            btn.setMenu(menu)
            bar_layout.addWidget(btn)

        add_btn = QPushButton("+ Add Track")
        add_menu = QMenu(self)
        add_menu.addAction("Signal", lambda: self._add_track(SignalTrack()))
        add_menu.addAction("Spectrogram", lambda: self._add_track(SpectrogramTrack()))
        add_menu.addAction("Filtered Band...", self._add_filtered_track)
        add_btn.setMenu(add_menu)
        bar_layout.addWidget(add_btn)
        bar_layout.addStretch()

    def _add_filtered_track(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Filtered Band")
        form = QFormLayout(dialog)

        low_spin = QDoubleSpinBox()
        low_spin.setRange(0.1, 10_000.0)
        low_spin.setValue(4.0)
        low_spin.setSuffix(" Hz")

        high_spin = QDoubleSpinBox()
        high_spin.setRange(0.1, 10_000.0)
        high_spin.setValue(40.0)
        high_spin.setSuffix(" Hz")

        form.addRow("Low cutoff", low_spin)
        form.addRow("High cutoff", high_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._add_track(FilteredTrack(low_spin.value(), high_spin.value()))

    # ------------------------------------------------------------------ #
    # Selection                                                             #
    # ------------------------------------------------------------------ #

    def _populate_channels(self, session: Session) -> None:
        self._channel_combo.blockSignals(True)
        self._channel_combo.clear()
        for name in session.channels.names:
            self._channel_combo.addItem(name)
        self._channel_combo.blockSignals(False)

    def _on_session_changed(self, index: int) -> None:
        if 0 <= index < len(self._sessions):
            self._populate_channels(self._sessions[index])
        self._rebuild()

    # ------------------------------------------------------------------ #
    # Figure rebuild                                                        #
    # ------------------------------------------------------------------ #

    def _rebuild(self) -> None:
        self._figure.clear()

        s_idx = self._session_combo.currentIndex()
        c_idx = self._channel_combo.currentIndex()

        if not self._sessions or s_idx < 0 or c_idx < 0 or not self._tracks:
            self._canvas.draw_idle()
            return

        session = self._sessions[s_idx]
        n = len(self._tracks)
        axes = []

        for i, track in enumerate(self._tracks):
            sharex = axes[0] if i > 0 else None
            ax = self._figure.add_subplot(n, 1, i + 1, sharex=sharex)
            axes.append(ax)
            track.render(ax, session, c_idx)

        for ax in axes[:-1]:
            ax.tick_params(labelbottom=False)
        axes[-1].set_xlabel("Time (s)")

        try:
            self._figure.tight_layout()
        except Exception:
            pass

        self._toolbar.update()  # reset nav stack so it doesn't hold stale axis refs
        self._canvas.draw_idle()

        n_sess = len(self._sessions)
        dur = session.timeline.duration
        n_ch = session.channels.n_channels
        n_ev = session.events.n_events
        self._info_label.setText(
            f"Session {s_idx + 1} of {n_sess} · {dur:.1f} s · {n_ch} channels · {n_ev} events"
        )
