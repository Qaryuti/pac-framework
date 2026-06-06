"""PAC Framework main window.

MainWindow is a thin hub that:
  - Owns shared state (_state, _selected_session_idx, _session_catalogs,
    _suppress_invalidation, _subjects_root)
  - Wires the toolbar buttons to Build / Generate / Save / Load actions
  - Validates config before Build
  - Delegates all tab UI and per-tab logic to three mixins

Tab logic lives in:
  pac_framework.gui.tabs.subject_designer  (_SubjectDesignerMixin)
  pac_framework.gui.tabs.signal_config     (_SignalConfigMixin)
  pac_framework.gui.tabs.data_browser      (_DataBrowserMixin)

Scientific pipeline lives in:
  pac_framework.generator.runner  (build_sessions, generate_signals)
"""
from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QTabWidget,
    QToolBar,
)

from pac_framework.generator.config import EventClass, SessionSpec, SignalConfig
from pac_framework.generator.runner import build_sessions, generate_signals
from pac_framework.gui._table_utils import _cell
from pac_framework.gui.persistence import load_subject, save_subject
from pac_framework.gui.subject_state import SubjectState
from pac_framework.gui.tabs.subject_designer import _today
from pac_framework.gui.tabs.data_browser import _DataBrowserMixin
from pac_framework.gui.tabs.signal_config import _SignalConfigMixin
from pac_framework.gui.tabs.subject_designer import (
    _DEFAULT_EVENTS_CATALOG,
    _SubjectDesignerMixin,
)

logger = logging.getLogger(__name__)


class MainWindow(
    _SubjectDesignerMixin,
    _SignalConfigMixin,
    _DataBrowserMixin,
    QMainWindow,
):
    def __init__(self) -> None:
        super().__init__()
        self._state: SubjectState | None = None
        self._subjects_root = Path.cwd() / "subjects"
        self._selected_session_idx: int = 0
        self._session_catalogs: list[list[dict]] = []
        self._suppress_invalidation: bool = False
        self._subjects_root.mkdir(parents=True, exist_ok=True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("PAC Framework")
        self.resize(1200, 800)
        self.menuBar()
        self.statusBar()

        toolbar = QToolBar("Actions")
        toolbar.setMovable(False)
        toolbar.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

        build_action = QAction("Build Timeline && Events", self)
        build_action.setShortcut(QKeySequence("Ctrl+B"))
        build_action.triggered.connect(self._on_build)
        toolbar.addAction(build_action)

        gen_action = QAction("Generate Signals", self)
        gen_action.setShortcut(QKeySequence("Ctrl+G"))
        gen_action.triggered.connect(self._on_generate)
        toolbar.addAction(gen_action)

        toolbar.addSeparator()

        save_action = QAction("Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save)
        toolbar.addAction(save_action)

        load_action = QAction("Load", self)
        load_action.setShortcut(QKeySequence("Ctrl+L"))
        load_action.triggered.connect(self._on_load)
        toolbar.addAction(load_action)

        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        config_widget = self._build_config_widget()
        scroll = QScrollArea()
        scroll.setWidget(config_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tabs.addTab(scroll, "Subject Designer")

        self._tabs.addTab(self._build_signal_config_tab(), "Signal Config")
        self._tabs.addTab(self._build_data_browser_tab(), "Data Browser")

        self._tabs.setCurrentIndex(0)
        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ------------------------------------------------------------------ #
    # Validation                                                           #
    # ------------------------------------------------------------------ #

    def _validate_catalog_list(
        self, catalog: list[dict], session_num: int
    ) -> list[dict]:
        names: list[str] = []
        validated: list[dict] = []
        for cls in catalog:
            name = cls.get("name", "").strip()
            if not name:
                raise ValueError(
                    f"Session {session_num} catalog: a class name is empty."
                )
            rate_hz = cls.get("rate_hz", 0.0)
            if rate_hz <= 0:
                raise ValueError(
                    f"Session {session_num} catalog ('{name}'):"
                    f" rate must be > 0, got {rate_hz}."
                )
            min_gap_sec = cls.get("min_gap_sec", 0.0)
            if min_gap_sec < 0:
                raise ValueError(
                    f"Session {session_num} catalog ('{name}'):"
                    f" min gap must be >= 0, got {min_gap_sec}."
                )
            names.append(name)
            validated.append({
                "name": name,
                "rate_hz": float(rate_hz),
                "min_gap_sec": float(min_gap_sec),
            })
        if len(set(names)) != len(names):
            dupes = sorted({n for n in names if names.count(n) > 1})
            raise ValueError(
                f"Session {session_num} catalog: duplicate class names: {dupes}."
            )
        return validated

    def _validate_full_config(
        self,
    ) -> tuple:
        """Validate all GUI inputs and return (channel_info, all_catalogs, session_specs).

        Raises ValueError with a user-readable message on any problem.
        """
        self._flush_catalog_to_store()

        if not self._name_edit.text().strip():
            raise ValueError("Subject name is empty.")
        notes = self._notes_edit.toPlainText()
        if len(notes) > 1000:
            raise ValueError(f"Notes exceed 1000 characters ({len(notes)} chars).")

        n_rows = self._session_table.rowCount()
        if n_rows < 1:
            raise ValueError("At least one session is required.")
        if self._sfreq_spin.value() <= 0:
            raise ValueError("Sample rate must be > 0.")

        while len(self._session_catalogs) < n_rows:
            self._session_catalogs.append([dict(c) for c in _DEFAULT_EVENTS_CATALOG])
        self._session_catalogs = self._session_catalogs[:n_rows]

        session_specs: list[dict] = []
        for r in range(n_rows):
            date_str = _cell(self._session_table, r, 0) or _today()
            dur_text = _cell(self._session_table, r, 1)
            task = _cell(self._session_table, r, 2) or "synthetic"
            try:
                duration_sec = float(dur_text)
            except ValueError:
                raise ValueError(
                    f"Session row {r + 1}: duration must be a number, got '{dur_text}'."
                )
            if duration_sec <= 0:
                raise ValueError(
                    f"Session row {r + 1}: duration must be > 0, got {duration_sec}."
                )
            session_specs.append({
                "date": date_str,
                "duration_sec": duration_sec,
                "task": task,
            })

        all_catalogs: list[list[dict]] = [
            self._validate_catalog_list(raw, i + 1)
            for i, raw in enumerate(self._session_catalogs)
        ]

        if self._shaft_table.rowCount() < 1:
            raise ValueError("Channel layout must have at least one shaft.")
        channel_info = self._build_channel_info()

        return channel_info, all_catalogs, session_specs

    # ------------------------------------------------------------------ #
    # Invalidation                                                         #
    # ------------------------------------------------------------------ #

    def _invalidate_signals(self) -> None:
        if (
            self._state is None
            or not self._state.signals_populated
            or self._suppress_invalidation
        ):
            return

        new_sessions = []
        for session in self._state.sessions:
            new_data = np.zeros_like(session.channels.data)
            new_channels = dataclasses.replace(session.channels, data=new_data)
            new_sessions.append(dataclasses.replace(session, channels=new_channels))

        self._state.sessions = new_sessions
        self._state.signals_populated = False
        self._viewer.populate(new_sessions)
        self.statusBar().showMessage(
            "Signals invalidated — regenerate to view updated data.", 5000
        )

    # ------------------------------------------------------------------ #
    # Actions                                                              #
    # ------------------------------------------------------------------ #

    def _on_build(self) -> None:
        try:
            channel_info, all_catalogs, session_specs = self._validate_full_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Configuration Error", str(exc))
            return

        subject_name = self._name_edit.text().strip()
        root_seed = self._seed_spin.value()
        sfreq = float(self._sfreq_spin.value())

        typed_specs = [
            SessionSpec(
                date=s["date"],
                duration_sec=s["duration_sec"],
                task=s["task"],
                event_catalog=tuple(
                    EventClass(name=ec["name"], rate_hz=ec["rate_hz"], min_gap_sec=ec["min_gap_sec"])
                    for ec in catalog
                ),
            )
            for s, catalog in zip(session_specs, all_catalogs)
        ]
        sessions = build_sessions(subject_name, root_seed, sfreq, typed_specs, channel_info)

        old_scs = self._state.session_signal_configs if self._state is not None else []
        new_scs = [
            old_scs[i] if i < len(old_scs) else SignalConfig()
            for i in range(len(sessions))
        ]

        self._state = SubjectState(
            subject_name=subject_name,
            master_seed=root_seed,
            notes=self._notes_edit.toPlainText(),
            sfreq=sfreq,
            sessions=sessions,
            channel_layout=self._get_shaft_layout(),
            session_signal_configs=new_scs,
            signals_populated=False,
        )
        self._viewer.populate(sessions)
        self._update_timeline_preview()
        self._refresh_populations_table()
        self._update_signal_config_session_label()
        self._sig_body.setEnabled(True)
        self._loaded_subject_label.setText(f"Built: {subject_name}")
        self._loaded_subject_label.setStyleSheet("color: black;")

    def _on_generate(self) -> None:
        if self._state is None:
            self.statusBar().showMessage("Run 'Build Timeline & Events' first.", 3000)
            return

        self._flush_populations_to_store()

        if not any(
            any(p.kind == "oscillator" for p in sc.populations)
            for sc in self._state.session_signal_configs
        ):
            self.statusBar().showMessage(
                "No oscillator populations configured; filling with zeros.", 3000
            )

        new_sessions = generate_signals(
            self._state.sessions,
            self._state.session_signal_configs,
            self._state.master_seed,
            self._state.subject_name,
        )

        self._state.sessions = new_sessions
        self._state.signals_populated = True
        self._viewer.populate(new_sessions)
        self._tabs.setCurrentIndex(2)

    def _on_save(self) -> None:
        if self._state is None:
            self.statusBar().showMessage("No subject to save.", 3000)
            return

        subject_name = self._name_edit.text().strip() or "subject_001"
        if subject_name != self._state.sessions[0].subject_id:
            self._state.sessions = [
                dataclasses.replace(s, subject_id=subject_name)
                for s in self._state.sessions
            ]
            self._state.subject_name = subject_name

        subject_dir = self._subjects_root / subject_name
        supplementary = {
            "sessions": self._read_session_specs(),
            "channel_layout": self._get_shaft_layout(),
            "signal": {},
        }
        try:
            save_subject(self._state, subject_dir, supplementary)
            self.statusBar().showMessage(f"Saved '{subject_name}' → {subject_dir}", 3000)
        except Exception as e:
            logger.error("Save failed: %s", e)
            QMessageBox.critical(self, "Save Error", str(e))

    def _on_load(self) -> None:
        subject_dir = QFileDialog.getExistingDirectory(
            self, "Select Subject Folder", str(self._subjects_root)
        )
        if not subject_dir:
            return

        try:
            state, supplementary = load_subject(Path(subject_dir))
        except Exception as e:
            logger.error("Load failed: %s", e)
            QMessageBox.critical(self, "Load Error", str(e))
            return

        self._apply_loaded_subject(state, supplementary)
        self._tabs.setCurrentIndex(2)
