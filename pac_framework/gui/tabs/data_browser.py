"""Data Browser tab mixin for MainWindow."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pac_framework.gui.widgets.tracked_viewer import TrackedViewer


class _DataBrowserMixin:
    """Provides the Data Browser tab widget."""

    def _build_data_browser_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(0, 4, 0, 0)
        vbox.setSpacing(4)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(4, 0, 4, 0)
        top_bar.addWidget(QLabel("Subject:"))

        self._browser_subject_combo = QComboBox()
        self._browser_subject_combo.setMinimumWidth(160)
        self._browser_subject_combo.currentTextChanged.connect(
            self._on_subject_combo_changed
        )
        top_bar.addWidget(self._browser_subject_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_all_subject_combos)
        top_bar.addWidget(refresh_btn)
        top_bar.addStretch()
        vbox.addLayout(top_bar)

        self._viewer = TrackedViewer()
        vbox.addWidget(self._viewer, stretch=1)

        return tab
