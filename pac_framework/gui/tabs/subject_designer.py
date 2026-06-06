"""Subject Designer tab mixin for MainWindow.

Owns all UI and logic for the Subject Designer tab:
  - Subject metadata (name, seed, notes, sample rate)
  - Session list + per-session event catalog
  - Channel layout (shafts)
  - channel_info DataFrame construction
"""
from __future__ import annotations

import logging
from datetime import date as _date
from datetime import timedelta

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pac_framework.generator.config import SignalConfig
from pac_framework.generator.runner import channel_info_from_shafts
from pac_framework.gui._table_utils import _cell, _make_table
from pac_framework.gui.widgets.timeline_preview import TimelinePreview

logger = logging.getLogger(__name__)

# ── module-level constants shared with main_window ────────────────────────────

_DEFAULT_SHAFTS = [
    ("LA", "amygdala", 8, 3.0),
    ("LH", "hippocampus", 8, 3.0),
]

_DEFAULT_EVENTS_CATALOG: list[dict] = [
    {"name": "cue_onset",     "rate_hz": 0.2, "min_gap_sec": 3.0},
    {"name": "decision_made", "rate_hz": 0.2, "min_gap_sec": 3.0},
    {"name": "outcome",       "rate_hz": 0.2, "min_gap_sec": 3.0},
]


def _today() -> str:
    return _date.today().isoformat()


def _default_sessions() -> list[tuple[str, float, str]]:
    return [
        ((_date.today() + timedelta(days=i)).isoformat(), 60.0, "synthetic")
        for i in range(3)
    ]


# ── mixin ─────────────────────────────────────────────────────────────────────

class _SubjectDesignerMixin:
    """Provides the Subject Designer tab widget and all related handlers."""

    # ── tab builder ───────────────────────────────────────────────────────

    def _build_config_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(6)
        layout.addWidget(self._build_subject_group())
        layout.addWidget(self._build_sessions_area())
        layout.addWidget(self._build_channel_layout_group())
        layout.addStretch()
        return widget

    def _build_subject_group(self) -> QGroupBox:
        group = QGroupBox("Subject")
        form = QFormLayout(group)

        self._name_edit = QLineEdit("subject_001")
        form.addRow("Name", self._name_edit)

        self._seed_spin = QSpinBox()
        self._seed_spin.setRange(0, 2_147_483_647)
        self._seed_spin.setValue(42)
        self._seed_spin.valueChanged.connect(lambda _: self._invalidate_signals())
        form.addRow("Seed", self._seed_spin)

        self._notes_edit = QPlainTextEdit()
        self._notes_edit.setPlaceholderText("Optional notes (max 1000 chars)")
        self._notes_edit.setMaximumHeight(72)
        form.addRow("Notes", self._notes_edit)

        return group

    # ── Sessions area ─────────────────────────────────────────────────────

    def _build_sessions_area(self) -> QGroupBox:
        group = QGroupBox("Sessions")
        vbox = QVBoxLayout(group)

        self._sfreq_spin = QSpinBox()
        self._sfreq_spin.setRange(1, 100_000)
        self._sfreq_spin.setValue(1000)
        self._sfreq_spin.setSuffix(" Hz")
        self._sfreq_spin.valueChanged.connect(lambda _: self._invalidate_signals())
        rate_form = QFormLayout()
        rate_form.addRow("Sample rate", self._sfreq_spin)
        vbox.addLayout(rate_form)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_session_list_panel())
        splitter.addWidget(self._build_session_detail_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 600])
        vbox.addWidget(splitter)

        for date_str, dur, task in _default_sessions():
            self._append_session_row(date_str, dur, task)
            self._session_catalogs.append([dict(c) for c in _DEFAULT_EVENTS_CATALOG])

        if self._session_table.rowCount() > 0:
            self._session_table.selectRow(0)
            self._load_catalog_from_store(0)
            self._update_detail_header(0)

        self._session_table.currentCellChanged.connect(
            lambda row, *_: self._on_session_row_selected(row)
        )
        self._session_table.itemChanged.connect(
            lambda item: self._invalidate_signals() if item.column() == 1 else None
        )

        return group

    def _build_session_list_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(0, 0, 4, 0)

        self._session_table = _make_table(
            ["Date (yyyy-MM-dd)", "Duration (s)", "Task"],
            min_height=120,
            col_widths={0: 96, 1: 74},
        )
        from PyQt6.QtWidgets import QTableWidget
        self._session_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        vbox.addWidget(self._session_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Session")
        add_btn.clicked.connect(self._on_add_session)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove_session)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        vbox.addLayout(btn_row)

        return panel

    def _build_session_detail_panel(self) -> QWidget:
        panel = QWidget()
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(4, 0, 0, 0)

        self._detail_header = QLabel("—")
        self._detail_header.setStyleSheet("font-weight: bold; padding: 2px 0;")
        vbox.addWidget(self._detail_header)

        cat_group = QGroupBox("Event Catalog")
        cat_vbox = QVBoxLayout(cat_group)

        self._event_table = _make_table(
            ["Class Name", "Rate (Hz)", "Min Gap (s)"],
            min_height=90,
            col_widths={0: 100, 1: 66},
        )
        self._event_table.itemChanged.connect(lambda _: self._invalidate_signals())
        cat_vbox.addWidget(self._event_table)

        cat_btn_row = QHBoxLayout()
        add_cls_btn = QPushButton("+ Add Event Class")
        add_cls_btn.clicked.connect(self._on_add_event_class)
        remove_cls_btn = QPushButton("Remove Selected")
        remove_cls_btn.clicked.connect(self._on_remove_event_class)
        cat_btn_row.addWidget(add_cls_btn)
        cat_btn_row.addWidget(remove_cls_btn)
        cat_vbox.addLayout(cat_btn_row)

        vbox.addWidget(cat_group)

        self._timeline_preview = TimelinePreview()
        self._timeline_preview.setMinimumHeight(90)
        self._timeline_preview.setMaximumHeight(120)
        vbox.addWidget(self._timeline_preview)

        return panel

    # ── session row management ────────────────────────────────────────────

    def _append_session_row(
        self, date_str: str, duration_sec: float, task: str
    ) -> None:
        row = self._session_table.rowCount()
        self._session_table.insertRow(row)
        self._session_table.setItem(row, 0, QTableWidgetItem(date_str))
        self._session_table.setItem(row, 1, QTableWidgetItem(str(duration_sec)))
        self._session_table.setItem(row, 2, QTableWidgetItem(task))

    def _on_add_session(self) -> None:
        self._flush_catalog_to_store()

        n = self._session_table.rowCount()
        if n > 0:
            last_date = _cell(self._session_table, n - 1, 0) or _today()
            try:
                next_date = (
                    _date.fromisoformat(last_date) + timedelta(days=1)
                ).isoformat()
            except ValueError:
                next_date = _today()
            try:
                dur = float(_cell(self._session_table, n - 1, 1))
            except ValueError:
                dur = 60.0
            task = _cell(self._session_table, n - 1, 2) or "synthetic"
        else:
            next_date, dur, task = _today(), 60.0, "synthetic"

        if 0 <= self._selected_session_idx < len(self._session_catalogs):
            new_catalog = [
                dict(c) for c in self._session_catalogs[self._selected_session_idx]
            ]
        else:
            new_catalog = [dict(c) for c in _DEFAULT_EVENTS_CATALOG]

        self._append_session_row(next_date, dur, task)
        self._session_catalogs.append(new_catalog)

        if self._state is not None:
            idx = self._selected_session_idx
            cfg = (
                self._state.session_signal_configs[idx]
                if idx < len(self._state.session_signal_configs)
                else SignalConfig()
            )
            self._state.session_signal_configs.append(
                SignalConfig(populations=list(cfg.populations), projection=cfg.projection)
            )

        self._invalidate_signals()

    def _on_remove_session(self) -> None:
        selected = self._session_table.selectionModel().selectedRows()
        if not selected:
            return
        if self._session_table.rowCount() - len(selected) < 1:
            QMessageBox.warning(self, "Cannot Remove", "Must keep at least one session.")
            return

        self._flush_catalog_to_store()

        for idx in sorted([r.row() for r in selected], reverse=True):
            self._session_table.removeRow(idx)
            if idx < len(self._session_catalogs):
                self._session_catalogs.pop(idx)
            if self._state is not None and idx < len(self._state.session_signal_configs):
                self._state.session_signal_configs.pop(idx)

        n = self._session_table.rowCount()
        self._selected_session_idx = min(self._selected_session_idx, n - 1)

        if n > 0:
            self._session_table.selectRow(self._selected_session_idx)
            self._load_catalog_from_store(self._selected_session_idx)
            self._update_detail_header(self._selected_session_idx)
            self._update_timeline_preview()
            self._refresh_populations_table()
            self._update_signal_config_session_label()

        self._invalidate_signals()

    def _on_session_row_selected(self, row: int) -> None:
        if row < 0 or row == self._selected_session_idx:
            return
        self._flush_catalog_to_store()
        self._flush_populations_to_store()
        self._selected_session_idx = row
        self._load_catalog_from_store(row)
        self._update_detail_header(row)
        self._update_timeline_preview()
        self._refresh_populations_table()
        self._update_signal_config_session_label()

    def _flush_catalog_to_store(self) -> None:
        idx = self._selected_session_idx
        if 0 <= idx < len(self._session_catalogs):
            self._session_catalogs[idx] = self._get_event_catalog()

    def _load_catalog_from_store(self, idx: int) -> None:
        catalog = (
            self._session_catalogs[idx]
            if 0 <= idx < len(self._session_catalogs)
            else []
        )
        self._event_table.blockSignals(True)
        self._event_table.setRowCount(0)
        for cls in catalog:
            self._append_event_row(
                cls.get("name", ""),
                cls.get("rate_hz", 0.1),
                cls.get("min_gap_sec", 1.0),
            )
        self._event_table.blockSignals(False)

    def _update_detail_header(self, idx: int) -> None:
        date_str = _cell(self._session_table, idx, 0, "—")
        task_str = _cell(self._session_table, idx, 2, "—")
        self._detail_header.setText(
            f"Session {idx + 1}  —  {task_str}  —  {date_str}"
        )

    def _update_timeline_preview(self) -> None:
        if (
            self._state is not None
            and self._selected_session_idx < len(self._state.sessions)
        ):
            self._timeline_preview.set_session(
                self._state.sessions[self._selected_session_idx]
            )
        else:
            self._timeline_preview.set_session(None)

    def _read_session_specs(self) -> list[dict]:
        self._flush_catalog_to_store()
        specs: list[dict] = []
        for r in range(self._session_table.rowCount()):
            date_str = _cell(self._session_table, r, 0) or _today()
            dur_text = _cell(self._session_table, r, 1, "60.0")
            task = _cell(self._session_table, r, 2) or "synthetic"
            try:
                duration_sec: float = float(dur_text)
            except ValueError:
                duration_sec = 60.0
            catalog = (
                self._session_catalogs[r]
                if r < len(self._session_catalogs)
                else []
            )
            specs.append({
                "date": date_str,
                "duration_sec": duration_sec,
                "task": task,
                "event_catalog": catalog,
            })
        return specs

    # ── event catalog ─────────────────────────────────────────────────────

    def _append_event_row(
        self, name: str, rate_hz: float, min_gap_sec: float
    ) -> None:
        row = self._event_table.rowCount()
        self._event_table.insertRow(row)
        self._event_table.setItem(row, 0, QTableWidgetItem(name))
        self._event_table.setItem(row, 1, QTableWidgetItem(str(rate_hz)))
        self._event_table.setItem(row, 2, QTableWidgetItem(str(min_gap_sec)))

    def _on_add_event_class(self) -> None:
        n = self._event_table.rowCount()
        self._append_event_row(f"event_{n}", 0.1, 1.0)

    def _on_remove_event_class(self) -> None:
        selected = self._event_table.selectionModel().selectedRows()
        if not selected:
            return
        for idx in sorted([r.row() for r in selected], reverse=True):
            self._event_table.removeRow(idx)

    def _get_event_catalog(self) -> list[dict]:
        result: list[dict] = []
        for r in range(self._event_table.rowCount()):
            name = _cell(self._event_table, r, 0)
            try:
                rate_hz = float(_cell(self._event_table, r, 1))
            except ValueError:
                rate_hz = 0.1
            try:
                min_gap_sec = float(_cell(self._event_table, r, 2))
            except ValueError:
                min_gap_sec = 1.0
            result.append({"name": name, "rate_hz": rate_hz, "min_gap_sec": min_gap_sec})
        return result

    # ── channel layout ────────────────────────────────────────────────────

    def _build_channel_layout_group(self) -> QGroupBox:
        group = QGroupBox("Channel Layout")
        vbox = QVBoxLayout(group)

        self._shaft_table = _make_table(
            ["Shaft Name", "Region", "Contacts", "Spacing (mm)"],
            min_height=90,
            col_widths={0: 72, 1: 86, 2: 58},
        )
        self._shaft_table.itemChanged.connect(lambda _: self._invalidate_signals())
        vbox.addWidget(self._shaft_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ Add Shaft")
        add_btn.clicked.connect(self._on_add_shaft)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._on_remove_shaft)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        vbox.addLayout(btn_row)

        for shaft, region, contacts, spacing in _DEFAULT_SHAFTS:
            self._append_shaft_row(shaft, region, contacts, spacing)

        return group

    def _append_shaft_row(
        self, shaft: str, region: str, contacts: int, spacing: float
    ) -> None:
        row = self._shaft_table.rowCount()
        self._shaft_table.insertRow(row)
        self._shaft_table.setItem(row, 0, QTableWidgetItem(shaft))
        self._shaft_table.setItem(row, 1, QTableWidgetItem(region))
        self._shaft_table.setItem(row, 2, QTableWidgetItem(str(contacts)))
        self._shaft_table.setItem(row, 3, QTableWidgetItem(str(spacing)))

    def _on_add_shaft(self) -> None:
        n = self._shaft_table.rowCount()
        self._append_shaft_row(f"shaft_{n}", "unknown", 8, 3.0)
        self._invalidate_signals()

    def _on_remove_shaft(self) -> None:
        selected = self._shaft_table.selectionModel().selectedRows()
        if not selected:
            return
        if self._shaft_table.rowCount() - len(selected) < 1:
            QMessageBox.warning(self, "Cannot Remove", "Must keep at least one shaft.")
            return
        for idx in sorted([r.row() for r in selected], reverse=True):
            self._shaft_table.removeRow(idx)
        self._invalidate_signals()

    def _build_channel_info(self) -> pd.DataFrame:
        """Parse the shaft table and delegate geometry to channel_info_from_shafts."""
        shaft_specs = self._get_shaft_layout()
        if not shaft_specs:
            raise ValueError("Channel layout must have at least one shaft.")
        shaft_names = [s["shaft"] for s in shaft_specs]
        if len(set(shaft_names)) != len(shaft_names):
            dupes = sorted({n for n in shaft_names if shaft_names.count(n) > 1})
            raise ValueError(f"Channel layout: duplicate shaft names: {dupes}.")
        return channel_info_from_shafts(shaft_specs)

    def _get_shaft_layout(self) -> list[dict]:
        result: list[dict] = []
        for r in range(self._shaft_table.rowCount()):
            shaft = _cell(self._shaft_table, r, 0)
            if not shaft:
                raise ValueError(f"Channel layout row {r + 1}: shaft name is empty.")
            region = _cell(self._shaft_table, r, 1)
            contacts_text = _cell(self._shaft_table, r, 2)
            spacing_text = _cell(self._shaft_table, r, 3)
            try:
                contacts = int(contacts_text)
            except ValueError:
                raise ValueError(
                    f"Channel layout row {r + 1} ('{shaft}'): contacts must be an integer,"
                    f" got '{contacts_text}'."
                )
            if contacts < 1:
                raise ValueError(
                    f"Channel layout row {r + 1} ('{shaft}'): contacts must be >= 1,"
                    f" got {contacts}."
                )
            try:
                spacing_mm = float(spacing_text)
            except ValueError:
                raise ValueError(
                    f"Channel layout row {r + 1} ('{shaft}'): spacing must be a number,"
                    f" got '{spacing_text}'."
                )
            if spacing_mm <= 0:
                raise ValueError(
                    f"Channel layout row {r + 1} ('{shaft}'): spacing must be > 0,"
                    f" got {spacing_mm}."
                )
            result.append({
                "shaft": shaft,
                "region": region,
                "contacts": contacts,
                "spacing_mm": spacing_mm,
            })
        return result

    def _get_regions_from_layout(self) -> list[str]:
        seen: set[str] = set()
        regions: list[str] = []
        for r in range(self._shaft_table.rowCount()):
            region = _cell(self._shaft_table, r, 1)
            if region and region not in seen:
                regions.append(region)
                seen.add(region)
        return regions or ["unknown"]

    def _restore_subject_designer_ui(
        self, state, supplementary: dict
    ) -> None:
        """Populate all Subject Designer widgets from a loaded state."""
        self._suppress_invalidation = True
        try:
            self._name_edit.setText(state.subject_name)
            self._seed_spin.setValue(state.master_seed)
            self._notes_edit.setPlainText(state.notes)
            self._sfreq_spin.setValue(int(state.sfreq))

            self._shaft_table.setRowCount(0)
            for shaft_def in supplementary.get("channel_layout", []):
                self._append_shaft_row(
                    shaft_def.get("shaft", ""),
                    shaft_def.get("region", ""),
                    int(shaft_def.get("contacts", 8)),
                    float(shaft_def.get("spacing_mm", 3.0)),
                )
            if self._shaft_table.rowCount() == 0:
                logger.warning(
                    "'channel_layout' missing from manifest; using default layout."
                )
                self.statusBar().showMessage(
                    "channel_layout missing; using defaults", 4000
                )

            try:
                self._session_table.currentCellChanged.disconnect()
            except RuntimeError:
                pass

            self._session_table.setRowCount(0)
            self._session_catalogs = []
            self._selected_session_idx = 0

            for sess_def in supplementary.get("sessions", []):
                self._append_session_row(
                    sess_def.get("date", _today()),
                    float(sess_def.get("duration_sec", 60.0)),
                    sess_def.get("task", "synthetic"),
                )
                self._session_catalogs.append(
                    sess_def.get(
                        "event_catalog",
                        [dict(c) for c in _DEFAULT_EVENTS_CATALOG],
                    )
                )

            if self._session_table.rowCount() == 0:
                logger.warning("'sessions' missing from manifest; using defaults.")
                self.statusBar().showMessage("sessions missing; using defaults", 4000)
                for date_str, dur, task in _default_sessions():
                    self._append_session_row(date_str, dur, task)
                    self._session_catalogs.append(
                        [dict(c) for c in _DEFAULT_EVENTS_CATALOG]
                    )

            self._session_table.selectRow(0)
            self._load_catalog_from_store(0)
            self._update_detail_header(0)

            self._session_table.currentCellChanged.connect(
                lambda row, *_: self._on_session_row_selected(row)
            )
        finally:
            self._suppress_invalidation = False

    @staticmethod
    def _make_group(title: str, rows: list[tuple[str, QWidget]]) -> QGroupBox:
        group = QGroupBox(title)
        form = QFormLayout(group)
        for label, widget in rows:
            form.addRow(label, widget)
        return group
