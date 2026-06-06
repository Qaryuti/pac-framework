"""Modal dialog for configuring event-driven chi modulations on a PAC coupling.

Each row specifies one EventModulation: which event label triggers the lift,
how high chi rises (peak_chi), over what window, with what onset latency and
edge taper fraction.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_COLUMNS = ["Event label", "Peak χ", "Window (s)", "Latency (s)", "Edge fraction"]
_COL_EVENT, _COL_CHI, _COL_WIN, _COL_LAT, _COL_EDGE = range(5)


class CouplingModulationDialog(QDialog):
    """Table-based editor for a list of EventModulation dicts.

    Parameters
    ----------
    event_labels : list[str]   Available event class names for the dropdown.
    entries      : list[dict]  Existing modulation entries (may be empty).
    parent       : QWidget     Optional parent widget.
    """

    def __init__(
        self,
        event_labels: list[str],
        entries: list[dict],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._event_labels = event_labels or ["(no events)"]
        self.setWindowTitle("Event Modulations")
        self.setMinimumWidth(560)
        self._build_ui()
        for entry in entries:
            self._add_row(entry)

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info = QLabel(
            "Each row lifts χ from its baseline to <b>Peak χ</b> for <b>Window (s)</b> "
            "seconds, starting <b>Latency (s)</b> after each event. "
            "Multiple rows are combined by max."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(
            _COL_EVENT, QHeaderView.ResizeMode.Stretch
        )
        for col in (_COL_CHI, _COL_WIN, _COL_LAT, _COL_EDGE):
            self._table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add row")
        add_btn.clicked.connect(self._add_default_row)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_selected_rows)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ── row management ────────────────────────────────────────────────────

    def _add_default_row(self) -> None:
        self._add_row({})

    def _add_row(self, entry: dict) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)

        combo = QComboBox()
        combo.addItems(self._event_labels)
        label = entry.get("event_label", "")
        if label in self._event_labels:
            combo.setCurrentText(label)
        self._table.setCellWidget(row, _COL_EVENT, combo)

        chi_spin = _double_spin(0.0, 1.0, step=0.05, decimals=2)
        chi_spin.setValue(float(entry.get("peak_chi", 0.8)))
        self._table.setCellWidget(row, _COL_CHI, chi_spin)

        win_spin = _double_spin(0.01, 300.0, step=0.1, decimals=2)
        win_spin.setValue(float(entry.get("window_sec", 1.0)))
        self._table.setCellWidget(row, _COL_WIN, win_spin)

        lat_spin = _double_spin(0.0, 60.0, step=0.05, decimals=3)
        lat_spin.setValue(float(entry.get("latency_sec", 0.0)))
        self._table.setCellWidget(row, _COL_LAT, lat_spin)

        edge_spin = _double_spin(0.0, 0.5, step=0.05, decimals=2)
        edge_spin.setValue(float(entry.get("edge_fraction", 0.25)))
        self._table.setCellWidget(row, _COL_EDGE, edge_spin)

    def _remove_selected_rows(self) -> None:
        rows = sorted(
            {idx.row() for idx in self._table.selectedIndexes()},
            reverse=True,
        )
        for r in rows:
            self._table.removeRow(r)

    # ── data out ──────────────────────────────────────────────────────────

    def get_entries(self) -> list[dict]:
        """Return the current table contents as a list of EventModulation dicts."""
        entries: list[dict] = []
        for row in range(self._table.rowCount()):
            combo = self._table.cellWidget(row, _COL_EVENT)
            chi_spin = self._table.cellWidget(row, _COL_CHI)
            win_spin = self._table.cellWidget(row, _COL_WIN)
            lat_spin = self._table.cellWidget(row, _COL_LAT)
            edge_spin = self._table.cellWidget(row, _COL_EDGE)
            entries.append({
                "event_label": combo.currentText(),
                "peak_chi": chi_spin.value(),
                "window_sec": win_spin.value(),
                "latency_sec": lat_spin.value(),
                "edge_fraction": edge_spin.value(),
            })
        return entries


# ── helpers ───────────────────────────────────────────────────────────────────

def _double_spin(lo: float, hi: float, step: float, decimals: int) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(lo, hi)
    spin.setSingleStep(step)
    spin.setDecimals(decimals)
    return spin
