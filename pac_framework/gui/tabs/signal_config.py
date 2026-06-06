"""Signal Config tab mixin for MainWindow.

Owns all UI and logic for the Signal Config tab:
  - Population tables (oscillators, backgrounds, line noise)
  - Coupling tables (PAC, PPC)
  - Projection config
  - Subject loading via combo box
"""
from __future__ import annotations

import logging
import math

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pac_framework.generator.config import (
    ArtifactConfig,
    BackgroundPopulation,
    BurstConfig,
    EventModulation,
    LineNoisePopulation,
    OscillatorPopulation,
    PAFDrift,
    PhaseToAmpCoupling,
    PhaseToPhaseCoupling,
    ProjectionConfig,
    SignalConfig,
    WaveformShape,
)
from pac_framework.gui._table_utils import _cell, _make_table
from pac_framework.gui.persistence import load_subject
from pac_framework.gui.widgets.coupling_modulation_dialog import CouplingModulationDialog
from pac_framework.gui.widgets.oscillator_advanced_dialog import (
    OscillatorAdvancedDialog,
    default_advanced_params,
)

logger = logging.getLogger(__name__)


class _SignalConfigMixin:
    """Provides the Signal Config tab widget and all related handlers."""

    # ── tab builder ───────────────────────────────────────────────────────

    def _build_signal_config_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setSpacing(6)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Load Subject:"))

        self._subject_combo = QComboBox()
        self._subject_combo.setMinimumWidth(160)
        top_bar.addWidget(self._subject_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_all_subject_combos)
        top_bar.addWidget(refresh_btn)

        self._loaded_subject_label = QLabel("(no subject loaded)")
        self._loaded_subject_label.setStyleSheet("color: gray;")
        top_bar.addWidget(self._loaded_subject_label)
        top_bar.addStretch()
        vbox.addLayout(top_bar)

        self._sig_body = QWidget()
        body_vbox = QVBoxLayout(self._sig_body)
        body_vbox.setSpacing(6)

        session_row = QHBoxLayout()
        session_row.addWidget(QLabel("Session:"))
        self._sig_session_combo = QComboBox()
        self._sig_session_combo.setMinimumWidth(220)
        session_row.addWidget(self._sig_session_combo)
        apply_all_btn = QPushButton("Apply to All Sessions")
        apply_all_btn.setToolTip(
            "Copy this session's populations and projection to every other session."
        )
        apply_all_btn.clicked.connect(self._apply_config_to_all_sessions)
        session_row.addWidget(apply_all_btn)
        session_row.addStretch()
        body_vbox.addLayout(session_row)

        body_vbox.addWidget(self._build_populations_area())
        body_vbox.addWidget(self._build_couplings_group())
        body_vbox.addWidget(self._build_projection_group())
        body_vbox.addStretch()

        self._sig_body.setEnabled(False)

        sig_scroll = QScrollArea()
        sig_scroll.setWidget(self._sig_body)
        sig_scroll.setWidgetResizable(True)
        sig_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        vbox.addWidget(sig_scroll)

        self._subject_combo.currentTextChanged.connect(self._on_subject_combo_changed)
        self._sig_session_combo.currentIndexChanged.connect(
            self._on_sig_session_combo_changed
        )

        return tab

    def _build_populations_area(self) -> QWidget:
        area = QWidget()
        vbox = QVBoxLayout(area)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(6)

        # ── Oscillators ───────────────────────────────────────────────
        osc_group = QGroupBox("Oscillators")
        osc_vbox = QVBoxLayout(osc_group)
        self._osc_table = _make_table(
            ["ID", "Center Freq (Hz)", "Bandwidth (Hz)", "Amplitude", "Region", "Advanced"],
            min_height=100,
            col_widths={0: 80, 1: 110, 2: 110, 3: 90, 4: 110},
        )
        self._osc_table.itemChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        osc_vbox.addWidget(self._osc_table)
        osc_btns = QHBoxLayout()
        add_osc = QPushButton("+ Add Oscillator")
        add_osc.clicked.connect(self._on_add_oscillator)
        rem_osc = QPushButton("Remove Selected")
        rem_osc.clicked.connect(self._on_remove_oscillator)
        osc_btns.addWidget(add_osc)
        osc_btns.addWidget(rem_osc)
        osc_vbox.addLayout(osc_btns)
        vbox.addWidget(osc_group)

        # ── Backgrounds (1/f) ─────────────────────────────────────────
        bg_group = QGroupBox("Backgrounds (1/f)")
        bg_vbox = QVBoxLayout(bg_group)
        self._bg_table = _make_table(
            ["ID", "Slope", "Knee (Hz)", "Amplitude"],
            min_height=80,
            col_widths={0: 70, 1: 70, 2: 70},
        )
        self._bg_table.itemChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        bg_vbox.addWidget(self._bg_table)
        bg_btns = QHBoxLayout()
        add_bg = QPushButton("+ Add Background")
        add_bg.clicked.connect(self._on_add_background)
        rem_bg = QPushButton("Remove Selected")
        rem_bg.clicked.connect(self._on_remove_background)
        bg_btns.addWidget(add_bg)
        bg_btns.addWidget(rem_bg)
        bg_vbox.addLayout(bg_btns)
        vbox.addWidget(bg_group)

        # ── Line Noise ────────────────────────────────────────────────
        ln_group = QGroupBox("Line Noise")
        ln_vbox = QVBoxLayout(ln_group)
        self._ln_table = _make_table(
            ["ID", "Frequency (Hz)", "Harmonics", "Amplitudes"],
            min_height=80,
            col_widths={0: 70, 1: 90, 2: 110},
        )
        self._ln_table.itemChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        ln_vbox.addWidget(self._ln_table)
        ln_btns = QHBoxLayout()
        add_ln = QPushButton("+ Add Line Noise")
        add_ln.clicked.connect(self._on_add_line_noise)
        rem_ln = QPushButton("Remove Selected")
        rem_ln.clicked.connect(self._on_remove_line_noise)
        ln_btns.addWidget(add_ln)
        ln_btns.addWidget(rem_ln)
        ln_vbox.addLayout(ln_btns)
        vbox.addWidget(ln_group)

        return area

    def _build_couplings_group(self) -> QGroupBox:
        group = QGroupBox("Couplings")
        vbox = QVBoxLayout(group)

        pac_label = QLabel("Phase-to-Amplitude (PAC)")
        pac_label.setStyleSheet("font-weight: bold;")
        vbox.addWidget(pac_label)

        self._coupling_table = _make_table(
            ["Driver", "Target", "χ", "φ₀ (deg)", "κ", "Modulation"],
            min_height=80,
            col_widths={0: 90, 1: 90, 2: 50, 3: 65, 4: 50},
        )
        self._coupling_table.itemChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        vbox.addWidget(self._coupling_table)

        pac_btn_row = QHBoxLayout()
        add_pac_btn = QPushButton("+ Add PAC")
        add_pac_btn.clicked.connect(self._on_add_coupling)
        rem_pac_btn = QPushButton("Remove Selected")
        rem_pac_btn.clicked.connect(self._on_remove_coupling)
        pac_btn_row.addWidget(add_pac_btn)
        pac_btn_row.addWidget(rem_pac_btn)
        vbox.addLayout(pac_btn_row)

        ppc_label = QLabel("Phase-to-Phase (PPC)")
        ppc_label.setStyleSheet("font-weight: bold;")
        vbox.addWidget(ppc_label)

        self._ppc_table = _make_table(
            ["Driver", "Target", "Strength", "Delay (ms)", "N:M"],
            min_height=80,
            col_widths={0: 90, 1: 90, 2: 65, 3: 70},
        )
        self._ppc_table.itemChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        vbox.addWidget(self._ppc_table)

        ppc_btn_row = QHBoxLayout()
        add_ppc_btn = QPushButton("+ Add PPC")
        add_ppc_btn.clicked.connect(self._on_add_ppc)
        rem_ppc_btn = QPushButton("Remove Selected")
        rem_ppc_btn.clicked.connect(self._on_remove_ppc)
        ppc_btn_row.addWidget(add_ppc_btn)
        ppc_btn_row.addWidget(rem_ppc_btn)
        vbox.addLayout(ppc_btn_row)

        return group

    def _build_projection_group(self) -> QGroupBox:
        group = QGroupBox("Projection")
        form = QFormLayout(group)

        self._proj_mode_combo = QComboBox()
        self._proj_mode_combo.addItems(["region_match", "all_identical"])
        self._proj_mode_combo.currentTextChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        form.addRow("Mode", self._proj_mode_combo)

        self._noise_sd_spin = QDoubleSpinBox()
        self._noise_sd_spin.setRange(0.0, 1_000.0)
        self._noise_sd_spin.setDecimals(2)
        self._noise_sd_spin.setValue(3.0)
        self._noise_sd_spin.valueChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        form.addRow("Channel noise σ", self._noise_sd_spin)

        return group

    # ── subject combo + loading ───────────────────────────────────────────

    def _on_tab_changed(self, index: int) -> None:
        if index in (1, 2):
            self._refresh_all_subject_combos()

    def _refresh_all_subject_combos(self) -> None:
        current_name = self._state.subject_name if self._state is not None else ""
        subjects = sorted(
            d.name
            for d in self._subjects_root.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        )
        for combo in (self._subject_combo, self._browser_subject_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("— select subject —")
            for name in subjects:
                combo.addItem(name)
            idx = combo.findText(current_name)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _on_subject_combo_changed(self, name: str) -> None:
        if not name or name.startswith("—"):
            return
        self._load_subject_into_state(name)

    def _load_subject_into_state(self, name: str) -> None:
        if self._state is not None and self._state.signals_populated:
            reply = QMessageBox.question(
                self,
                "Discard signals?",
                f"Discard current signals and load '{name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                self._subject_combo.blockSignals(True)
                current_name = self._state.subject_name if self._state else ""
                idx = self._subject_combo.findText(current_name)
                self._subject_combo.setCurrentIndex(idx if idx >= 0 else 0)
                self._subject_combo.blockSignals(False)
                return

        subject_dir = self._subjects_root / name
        try:
            state, supplementary = load_subject(subject_dir)
        except Exception as e:
            logger.error("Load failed: %s", e)
            QMessageBox.critical(self, "Load Error", str(e))
            return

        self._apply_loaded_subject(state, supplementary)

    def _apply_loaded_subject(self, state, supplementary: dict) -> None:
        self._state = state
        self._viewer.populate(state.sessions)
        self._restore_subject_designer_ui(state, supplementary)
        self._refresh_populations_table()
        self._update_signal_config_session_label()
        self._sig_body.setEnabled(True)
        self._loaded_subject_label.setText(f"Loaded: {state.subject_name}")
        self._loaded_subject_label.setStyleSheet("color: black;")
        self._refresh_all_subject_combos()
        self._update_timeline_preview()
        self.statusBar().showMessage(f"Loaded '{state.subject_name}'", 3000)

    # ── session combo (Signal Config tab) ─────────────────────────────────

    def _refresh_sig_session_combo(self) -> None:
        self._sig_session_combo.blockSignals(True)
        self._sig_session_combo.clear()
        for r in range(self._session_table.rowCount()):
            date_str = _cell(self._session_table, r, 0, "—")
            task_str = _cell(self._session_table, r, 2, "—")
            self._sig_session_combo.addItem(
                f"Session {r + 1}  —  {task_str}  —  {date_str}"
            )
        target = min(self._selected_session_idx, self._sig_session_combo.count() - 1)
        self._sig_session_combo.setCurrentIndex(max(target, 0))
        self._sig_session_combo.blockSignals(False)

    def _update_signal_config_session_label(self) -> None:
        self._refresh_sig_session_combo()

    def _on_sig_session_combo_changed(self, index: int) -> None:
        if index < 0 or index == self._selected_session_idx:
            return
        self._flush_catalog_to_store()
        self._flush_populations_to_store()
        self._selected_session_idx = index
        self._session_table.selectRow(index)
        self._load_catalog_from_store(index)
        self._update_detail_header(index)
        self._update_timeline_preview()
        self._refresh_populations_table()

    def _apply_config_to_all_sessions(self) -> None:
        if self._state is None:
            return
        self._flush_populations_to_store()
        idx = self._selected_session_idx
        n = len(self._state.sessions)
        if n <= 1:
            self.statusBar().showMessage("Only one session — nothing to copy to.", 3000)
            return
        source = (
            self._state.session_signal_configs[idx]
            if idx < len(self._state.session_signal_configs)
            else SignalConfig()
        )
        for i in range(n):
            if i != idx:
                while len(self._state.session_signal_configs) <= i:
                    self._state.session_signal_configs.append(SignalConfig())
                self._state.session_signal_configs[i] = source
        self._invalidate_signals()
        self.statusBar().showMessage(
            f"Config from Session {idx + 1} applied to all {n} sessions.", 3000
        )

    # ── populations tables ────────────────────────────────────────────────

    def _refresh_populations_table(self) -> None:
        self._suppress_invalidation = True
        defaults_written: SignalConfig | None = None
        idx = self._selected_session_idx
        try:
            if self._state is None:
                return
            regions = self._get_regions_from_layout()
            configs = self._state.session_signal_configs
            sc = configs[idx] if idx < len(configs) else SignalConfig()

            populations = list(sc.populations)
            if not populations:
                populations = [OscillatorPopulation(
                    id="osc_0",
                    center_frequency=10.0,
                    bandwidth=5.0,
                    amplitude=1.0,
                    region=regions[0] if regions else "unknown",
                )]
                defaults_written = SignalConfig(
                    populations=populations,
                    projection=sc.projection,
                )

            self._proj_mode_combo.blockSignals(True)
            self._proj_mode_combo.setCurrentText(sc.projection.mode)
            self._proj_mode_combo.blockSignals(False)
            self._noise_sd_spin.blockSignals(True)
            self._noise_sd_spin.setValue(sc.projection.channel_noise_sd)
            self._noise_sd_spin.blockSignals(False)

            self._populate_population_tables(populations, regions)

            osc_ids = [p.id for p in populations if isinstance(p, OscillatorPopulation)]
            self._coupling_table.setRowCount(0)
            self._ppc_table.setRowCount(0)
            for c in sc.couplings:
                if c.kind == "phase_to_amplitude":
                    self._append_coupling_row(
                        c.driver, c.target,
                        c.chi, math.degrees(c.phi_0), c.kappa,
                        osc_ids,
                        mod_entries=[m.model_dump() for m in c.event_modulations],
                    )
                elif c.kind == "phase_to_phase":
                    n, m = c.n_to_m_ratio
                    self._append_ppc_row(
                        c.driver, c.target,
                        c.coupling_strength, c.delay_ms,
                        f"{n}:{m}", osc_ids,
                    )
        finally:
            self._suppress_invalidation = False

        if defaults_written is not None and self._state is not None:
            while len(self._state.session_signal_configs) <= idx:
                self._state.session_signal_configs.append(SignalConfig())
            self._state.session_signal_configs[idx] = defaults_written

    def _populate_population_tables(
        self, populations: list, regions: list[str]
    ) -> None:
        self._osc_table.setRowCount(0)
        self._bg_table.setRowCount(0)
        self._ln_table.setRowCount(0)
        for pop in populations:
            if isinstance(pop, OscillatorPopulation):
                adv = {
                    "sharpness": pop.waveform_shape.peak_trough_sharpness,
                    "asymmetry": pop.waveform_shape.rise_decay_asymmetry,
                    "paf_sigma": pop.paf_drift.sigma_hz,
                    "paf_tau": pop.paf_drift.tau_seconds,
                    "burst_mode": pop.burst.mode,
                    "burst_rate": pop.burst.rate_hz,
                    "burst_dur_mean": pop.burst.duration_cycles_mean,
                    "burst_dur_sd": pop.burst.duration_cycles_sd,
                    "burst_refractory": pop.burst.refractory_cycles,
                    "artifact_rate": pop.artifact.rate_hz,
                    "artifact_amp_mult": pop.artifact.amplitude_mult,
                    "artifact_width": pop.artifact.width_samples,
                }
                self._append_oscillator_row(
                    pop.id, pop.center_frequency, pop.bandwidth,
                    pop.amplitude, pop.region, regions,
                    adv_params=adv,
                )
            elif isinstance(pop, BackgroundPopulation):
                self._append_background_row(pop.id, pop.slope, pop.knee_hz, pop.amplitude)
            elif isinstance(pop, LineNoisePopulation):
                self._append_line_noise_row(
                    pop.id, pop.frequency,
                    pop.harmonics, pop.amplitude_per_harmonic,
                )
            else:
                logger.warning("Unknown population kind in stored config: %r", pop)

    # ── per-kind row appenders ────────────────────────────────────────────

    def _append_oscillator_row(
        self,
        pop_id: str,
        center_freq: float,
        bandwidth: float,
        amplitude: float,
        region: str,
        regions: list[str],
        adv_params: dict | None = None,
    ) -> None:
        row = self._osc_table.rowCount()
        self._osc_table.insertRow(row)
        self._osc_table.setItem(row, 0, QTableWidgetItem(pop_id))
        self._osc_table.setItem(row, 1, QTableWidgetItem(str(center_freq)))
        self._osc_table.setItem(row, 2, QTableWidgetItem(str(bandwidth)))
        self._osc_table.setItem(row, 3, QTableWidgetItem(str(amplitude)))

        region_combo = QComboBox()
        region_combo.addItems(regions)
        if region in regions:
            region_combo.setCurrentText(region)
        region_combo.currentTextChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        self._osc_table.setCellWidget(row, 4, region_combo)

        params = {**default_advanced_params(), **(adv_params or {})}
        adv_btn = QPushButton("Advanced…")
        adv_btn._adv_params = params
        adv_btn.clicked.connect(lambda _checked, b=adv_btn: self._on_adv_btn_clicked(b))
        self._osc_table.setCellWidget(row, 5, adv_btn)

    def _on_adv_btn_clicked(self, btn: QPushButton) -> None:
        dlg = OscillatorAdvancedDialog(btn._adv_params, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            btn._adv_params = dlg.get_params()
            self._apply_populations_to_current_session()

    def _append_background_row(
        self, pop_id: str, slope: float, knee_hz: float, amplitude: float
    ) -> None:
        row = self._bg_table.rowCount()
        self._bg_table.insertRow(row)
        self._bg_table.setItem(row, 0, QTableWidgetItem(pop_id))
        self._bg_table.setItem(row, 1, QTableWidgetItem(str(slope)))
        self._bg_table.setItem(row, 2, QTableWidgetItem(str(knee_hz)))
        self._bg_table.setItem(row, 3, QTableWidgetItem(str(amplitude)))

    def _append_line_noise_row(
        self,
        pop_id: str,
        frequency: float,
        harmonics: list[int],
        amplitudes: list[float],
    ) -> None:
        row = self._ln_table.rowCount()
        self._ln_table.insertRow(row)
        self._ln_table.setItem(row, 0, QTableWidgetItem(pop_id))
        self._ln_table.setItem(row, 1, QTableWidgetItem(str(frequency)))
        self._ln_table.setItem(row, 2, QTableWidgetItem(", ".join(str(h) for h in harmonics)))
        self._ln_table.setItem(row, 3, QTableWidgetItem(", ".join(str(a) for a in amplitudes)))

    # ── per-kind readers ──────────────────────────────────────────────────

    def _read_oscillators(self) -> list[OscillatorPopulation]:
        pops: list[OscillatorPopulation] = []
        regions = self._get_regions_from_layout()
        for r in range(self._osc_table.rowCount()):
            pop_id = _cell(self._osc_table, r, 0) or f"osc_{r}"
            region_w = self._osc_table.cellWidget(r, 4)
            region = (
                region_w.currentText() if isinstance(region_w, QComboBox)
                else (regions[0] if regions else "unknown")
            )
            adv_btn = self._osc_table.cellWidget(r, 5)
            adv = {
                **default_advanced_params(),
                **(adv_btn._adv_params if isinstance(adv_btn, QPushButton) else {}),
            }
            try:
                cf = float(_cell(self._osc_table, r, 1) or "1.0")
                bw = float(_cell(self._osc_table, r, 2) or "1.0")
                amp = float(_cell(self._osc_table, r, 3) or "1.0")
            except ValueError:
                logger.warning("Oscillator row %d has non-numeric values; skipping.", r)
                continue
            if cf <= 0 or bw < 0 or amp <= 0:
                continue
            try:
                pops.append(OscillatorPopulation(
                    id=pop_id,
                    center_frequency=cf,
                    bandwidth=bw,
                    amplitude=amp,
                    region=region,
                    waveform_shape=WaveformShape(
                        peak_trough_sharpness=max(-1.0, min(1.0, adv["sharpness"])),
                        rise_decay_asymmetry=max(-1.0, min(1.0, adv["asymmetry"])),
                    ),
                    paf_drift=PAFDrift(
                        sigma_hz=max(0.0, adv["paf_sigma"]),
                        tau_seconds=max(0.01, adv["paf_tau"]),
                    ),
                    burst=BurstConfig(
                        mode=adv["burst_mode"],
                        rate_hz=max(0.01, adv["burst_rate"]),
                        duration_cycles_mean=max(0.01, adv["burst_dur_mean"]),
                        duration_cycles_sd=max(0.0, adv["burst_dur_sd"]),
                        refractory_cycles=max(0.0, adv["burst_refractory"]),
                    ),
                    artifact=ArtifactConfig(
                        rate_hz=max(0.0, adv["artifact_rate"]),
                        amplitude_mult=max(0.01, adv["artifact_amp_mult"]),
                        width_samples=max(1, int(adv["artifact_width"])),
                    ),
                ))
            except Exception:
                logger.warning("Oscillator row %d failed validation; skipping.", r)
                continue
        return pops

    def _read_backgrounds(self) -> list[BackgroundPopulation]:
        pops: list[BackgroundPopulation] = []
        for r in range(self._bg_table.rowCount()):
            pop_id = _cell(self._bg_table, r, 0) or f"bg_{r}"
            try:
                slope = float(_cell(self._bg_table, r, 1) or "1.5")
                knee_hz = float(_cell(self._bg_table, r, 2) or "0.0")
                amp = float(_cell(self._bg_table, r, 3) or "1.0")
            except ValueError:
                continue
            if slope <= 0 or amp <= 0:
                continue
            try:
                pops.append(BackgroundPopulation(id=pop_id, slope=slope, knee_hz=knee_hz, amplitude=amp))
            except Exception:
                continue
        return pops

    def _read_line_noises(self) -> list[LineNoisePopulation]:
        pops: list[LineNoisePopulation] = []
        for r in range(self._ln_table.rowCount()):
            pop_id = _cell(self._ln_table, r, 0) or f"ln_{r}"
            try:
                frequency = float(_cell(self._ln_table, r, 1) or "60.0")
            except ValueError:
                continue
            if frequency <= 0:
                continue
            harmonics_str = _cell(self._ln_table, r, 2)
            amplitudes_str = _cell(self._ln_table, r, 3)
            try:
                harmonics = [int(x.strip()) for x in harmonics_str.split(",") if x.strip()]
                amplitudes = [float(x.strip()) for x in amplitudes_str.split(",") if x.strip()]
            except ValueError:
                continue
            if len(harmonics) != len(amplitudes):
                continue
            try:
                pops.append(LineNoisePopulation(
                    id=pop_id, frequency=frequency,
                    harmonics=harmonics, amplitude_per_harmonic=amplitudes,
                ))
            except Exception:
                continue
        return pops

    def _read_all_populations(self) -> list:
        return [*self._read_oscillators(), *self._read_backgrounds(), *self._read_line_noises()]

    # ── coupling table ────────────────────────────────────────────────────

    def _append_coupling_row(
        self,
        driver: str,
        target: str,
        chi: float,
        phi_0_deg: float,
        kappa: float,
        osc_ids: list[str],
        mod_entries: list[dict] | None = None,
    ) -> None:
        row = self._coupling_table.rowCount()
        self._coupling_table.insertRow(row)

        driver_combo = QComboBox()
        driver_combo.addItems(osc_ids)
        if driver in osc_ids:
            driver_combo.setCurrentText(driver)
        driver_combo.currentTextChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        self._coupling_table.setCellWidget(row, 0, driver_combo)

        target_combo = QComboBox()
        target_combo.addItems(osc_ids)
        if target in osc_ids:
            target_combo.setCurrentText(target)
        target_combo.currentTextChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        self._coupling_table.setCellWidget(row, 1, target_combo)

        self._coupling_table.setItem(row, 2, QTableWidgetItem(str(chi)))
        self._coupling_table.setItem(row, 3, QTableWidgetItem(str(phi_0_deg)))
        self._coupling_table.setItem(row, 4, QTableWidgetItem(str(kappa)))

        mod_btn = QPushButton("Modulation…")
        mod_btn._mod_entries = list(mod_entries or [])
        mod_btn.clicked.connect(
            lambda _checked, b=mod_btn: self._on_coupling_mod_btn_clicked(b)
        )
        self._coupling_table.setCellWidget(row, 5, mod_btn)

    def _read_couplings(self) -> list[PhaseToAmpCoupling]:
        couplings: list[PhaseToAmpCoupling] = []
        for r in range(self._coupling_table.rowCount()):
            driver_w = self._coupling_table.cellWidget(r, 0)
            target_w = self._coupling_table.cellWidget(r, 1)
            if not (isinstance(driver_w, QComboBox) and isinstance(target_w, QComboBox)):
                continue
            driver = driver_w.currentText()
            target = target_w.currentText()
            if not driver or not target or driver == target:
                continue
            try:
                chi = float(_cell(self._coupling_table, r, 2) or "0.5")
                phi_0_deg = float(_cell(self._coupling_table, r, 3) or "0.0")
                kappa = float(_cell(self._coupling_table, r, 4) or "2.0")
            except ValueError:
                continue
            mod_btn = self._coupling_table.cellWidget(r, 5)
            raw_mods = getattr(mod_btn, "_mod_entries", []) if mod_btn else []
            event_mods: list[EventModulation] = []
            for em in raw_mods:
                try:
                    event_mods.append(EventModulation(**em))
                except Exception:
                    pass
            try:
                couplings.append(PhaseToAmpCoupling(
                    driver=driver, target=target,
                    chi=chi, phi_0=math.radians(phi_0_deg), kappa=kappa,
                    event_modulations=tuple(event_mods),
                ))
            except Exception:
                continue
        return couplings

    def _on_coupling_mod_btn_clicked(self, btn: QPushButton) -> None:
        event_labels = self._get_current_event_labels()
        dlg = CouplingModulationDialog(event_labels, btn._mod_entries, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            btn._mod_entries = dlg.get_entries()
            self._apply_populations_to_current_session()

    def _get_current_event_labels(self) -> list[str]:
        catalogs = getattr(self, "_session_catalogs", [])
        idx = getattr(self, "_selected_session_idx", 0)
        if not catalogs or idx >= len(catalogs):
            return []
        return [cls["name"] for cls in catalogs[idx]]

    # ── PPC helpers ───────────────────────────────────────────────────────

    def _append_ppc_row(
        self,
        driver: str,
        target: str,
        strength: float,
        delay_ms: float,
        n_to_m: str,
        osc_ids: list[str],
    ) -> None:
        row = self._ppc_table.rowCount()
        self._ppc_table.insertRow(row)

        driver_combo = QComboBox()
        driver_combo.addItems(osc_ids)
        if driver in osc_ids:
            driver_combo.setCurrentText(driver)
        driver_combo.currentTextChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        self._ppc_table.setCellWidget(row, 0, driver_combo)

        target_combo = QComboBox()
        target_combo.addItems(osc_ids)
        if target in osc_ids:
            target_combo.setCurrentText(target)
        target_combo.currentTextChanged.connect(
            lambda _: self._apply_populations_to_current_session()
        )
        self._ppc_table.setCellWidget(row, 1, target_combo)

        self._ppc_table.setItem(row, 2, QTableWidgetItem(str(strength)))
        self._ppc_table.setItem(row, 3, QTableWidgetItem(str(delay_ms)))
        self._ppc_table.setItem(row, 4, QTableWidgetItem(n_to_m))

    def _read_ppc_couplings(self) -> list[PhaseToPhaseCoupling]:
        couplings: list[PhaseToPhaseCoupling] = []
        for r in range(self._ppc_table.rowCount()):
            driver_w = self._ppc_table.cellWidget(r, 0)
            target_w = self._ppc_table.cellWidget(r, 1)
            if not (isinstance(driver_w, QComboBox) and isinstance(target_w, QComboBox)):
                continue
            driver = driver_w.currentText()
            target = target_w.currentText()
            if not driver or not target or driver == target:
                continue
            try:
                strength = max(0.0, min(1.0, float(_cell(self._ppc_table, r, 2) or "0.3")))
                delay_ms = max(0.0, float(_cell(self._ppc_table, r, 3) or "15.0"))
                nm_str = _cell(self._ppc_table, r, 4) or "1:1"
                parts = nm_str.split(":")
                n_val = max(1, int(parts[0].strip()))
                m_val = max(1, int(parts[1].strip())) if len(parts) > 1 else 1
            except (ValueError, IndexError):
                continue
            try:
                couplings.append(PhaseToPhaseCoupling(
                    driver=driver, target=target,
                    coupling_strength=strength,
                    delay_ms=delay_ms,
                    n_to_m_ratio=(n_val, m_val),
                ))
            except Exception:
                continue
        return couplings

    def _on_add_ppc(self) -> None:
        osc_ids = [_cell(self._osc_table, r, 0) for r in range(self._osc_table.rowCount())]
        osc_ids = [oid for oid in osc_ids if oid]
        if len(osc_ids) < 2:
            self.statusBar().showMessage(
                "Need at least two oscillator populations to add a PPC coupling.", 3000
            )
            return
        self._append_ppc_row(osc_ids[0], osc_ids[1], 0.3, 15.0, "1:1", osc_ids)

    def _on_remove_ppc(self) -> None:
        selected = self._ppc_table.selectionModel().selectedRows()
        if not selected:
            return
        for idx in sorted([r.row() for r in selected], reverse=True):
            self._ppc_table.removeRow(idx)
        self._apply_populations_to_current_session()

    def _refresh_coupling_combos(self) -> None:
        osc_ids = []
        for r in range(self._osc_table.rowCount()):
            oid = _cell(self._osc_table, r, 0)
            if oid:
                osc_ids.append(oid)
        for table in (self._coupling_table, self._ppc_table):
            for r in range(table.rowCount()):
                for col in (0, 1):
                    combo_w = table.cellWidget(r, col)
                    if isinstance(combo_w, QComboBox):
                        current = combo_w.currentText()
                        combo_w.blockSignals(True)
                        combo_w.clear()
                        combo_w.addItems(osc_ids)
                        if current in osc_ids:
                            combo_w.setCurrentText(current)
                        combo_w.blockSignals(False)

    def _on_add_coupling(self) -> None:
        osc_ids = [_cell(self._osc_table, r, 0) for r in range(self._osc_table.rowCount())]
        osc_ids = [oid for oid in osc_ids if oid]
        if len(osc_ids) < 2:
            self.statusBar().showMessage(
                "Need at least two oscillator populations to add a coupling.", 3000
            )
            return
        self._append_coupling_row(osc_ids[0], osc_ids[1], 0.5, 0.0, 2.0, osc_ids)

    def _on_remove_coupling(self) -> None:
        selected = self._coupling_table.selectionModel().selectedRows()
        if not selected:
            return
        for idx in sorted([r.row() for r in selected], reverse=True):
            self._coupling_table.removeRow(idx)
        self._apply_populations_to_current_session()

    # ── add / remove handlers ─────────────────────────────────────────────

    def _on_add_oscillator(self) -> None:
        regions = self._get_regions_from_layout()
        n = self._osc_table.rowCount()
        self._append_oscillator_row(
            f"osc_{n}", 10.0, 5.0, 1.0,
            regions[0] if regions else "unknown", regions,
        )

    def _on_add_background(self) -> None:
        n = self._bg_table.rowCount()
        self._append_background_row(f"bg_{n}", 1.5, 0.0, 1.0)

    def _on_add_line_noise(self) -> None:
        n = self._ln_table.rowCount()
        self._append_line_noise_row(f"ln_{n}", 60.0, [1, 2, 3], [1.0, 0.3, 0.1])

    def _on_remove_oscillator(self) -> None:
        selected = self._osc_table.selectionModel().selectedRows()
        if not selected:
            return
        for idx in sorted([r.row() for r in selected], reverse=True):
            self._osc_table.removeRow(idx)
        self._apply_populations_to_current_session()

    def _on_remove_background(self) -> None:
        selected = self._bg_table.selectionModel().selectedRows()
        if not selected:
            return
        for idx in sorted([r.row() for r in selected], reverse=True):
            self._bg_table.removeRow(idx)
        self._apply_populations_to_current_session()

    def _on_remove_line_noise(self) -> None:
        selected = self._ln_table.selectionModel().selectedRows()
        if not selected:
            return
        for idx in sorted([r.row() for r in selected], reverse=True):
            self._ln_table.removeRow(idx)
        self._apply_populations_to_current_session()

    def _flush_populations_to_store(self) -> None:
        if self._state is None or self._suppress_invalidation:
            return
        pops = self._read_all_populations()
        pac_couplings = self._read_couplings()
        ppc_couplings = self._read_ppc_couplings()

        pop_ids = {p.id for p in pops}
        safe_pac = [
            c for c in pac_couplings
            if c.driver in pop_ids and c.target in pop_ids and c.driver != c.target
        ]
        safe_ppc = [
            c for c in ppc_couplings
            if c.driver in pop_ids and c.target in pop_ids and c.driver != c.target
        ]

        idx = self._selected_session_idx
        try:
            sc = SignalConfig(
                populations=pops,
                couplings=[*safe_pac, *safe_ppc],
                projection=ProjectionConfig(
                    mode=self._proj_mode_combo.currentText(),
                    channel_noise_sd=self._noise_sd_spin.value(),
                ),
            )
        except Exception:
            sc = SignalConfig(
                populations=pops,
                projection=ProjectionConfig(
                    mode=self._proj_mode_combo.currentText(),
                    channel_noise_sd=self._noise_sd_spin.value(),
                ),
            )

        while len(self._state.session_signal_configs) <= idx:
            self._state.session_signal_configs.append(SignalConfig())
        self._state.session_signal_configs[idx] = sc

    def _apply_populations_to_current_session(self) -> None:
        self._flush_populations_to_store()
        self._refresh_coupling_combos()
        self._invalidate_signals()
