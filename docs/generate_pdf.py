"""Generate PAC Framework technical documentation PDF."""
from fpdf import FPDF


class Doc(FPDF):
    MARGIN = 18
    BODY_W = 174  # 210 - 2*18

    def __init__(self):
        super().__init__()
        self.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        self.set_auto_page_break(True, margin=self.MARGIN)

    # -- header / footer ----------------------------------------------------

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 5, "PAC Framework  -  Signal Generation Reference", align="L")
        self.ln(3)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.2)
        self.line(self.MARGIN, self.get_y(), 210 - self.MARGIN, self.get_y())
        self.ln(3)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 5, f"Page {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    # -- helpers ------------------------------------------------------------

    def cover(self):
        self.add_page()
        self.set_fill_color(20, 40, 80)
        self.rect(0, 0, 210, 297, "F")
        self.set_y(70)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(255, 255, 255)
        self.cell(0, 12, "PAC Framework", align="C")
        self.ln(14)
        self.set_font("Helvetica", "", 15)
        self.cell(0, 8, "Signal Generation Reference", align="C")
        self.ln(8)
        self.cell(0, 8, "A complete guide to synthetic iEEG generation", align="C")
        self.ln(8)
        self.cell(0, 8, "with phase-amplitude coupling", align="C")
        self.ln(30)
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(180, 200, 230)
        self.cell(0, 6, "Version 0.10.0  |  Schema version 0.10.0", align="C")
        self.set_text_color(0, 0, 0)

    def toc_page(self):
        self.add_page()
        self.h1("Table of Contents")
        entries = [
            ("1.", "Overview & Architecture", ""),
            ("2.", "The Signal Pipeline  -  Step by Step", ""),
            ("3.", "Oscillator Populations", ""),
            ("     3.1", "Frequency Drift (PAF Drift)", ""),
            ("     3.2", "Waveform Shape (Harmonic Injection)", ""),
            ("     3.3", "Burst Mode", ""),
            ("     3.4", "Artifacts", ""),
            ("4.", "Background (1/f) Populations", ""),
            ("5.", "Line Noise Populations", ""),
            ("6.", "Couplings", ""),
            ("     6.1", "Phase-to-Amplitude Coupling (PAC)", ""),
            ("     6.2", "Event-Modulated Coupling Depth", ""),
            ("     6.3", "Phase-to-Phase Coupling (PPC)", ""),
            ("7.", "Population-to-Channel Projection", ""),
            ("8.", "Per-Channel Independent Noise", ""),
            ("9.", "Ground-Truth Bundle", ""),
            ("10.", "Experiment Design  -  Sessions & Events", ""),
            ("11.", "Using the GUI  -  Tab by Tab", ""),
            ("     11.1", "Subject Designer Tab", ""),
            ("     11.2", "Signal Config Tab", ""),
            ("     11.3", "Data Browser Tab", ""),
            ("12.", "Programmatic API (no GUI)", ""),
            ("13.", "Saving & Loading Subjects", ""),
            ("14.", "Deterministic Reproducibility", ""),
            ("15.", "Parameter Quick Reference", ""),
        ]
        self.set_font("Helvetica", "", 10)
        for num, title, _ in entries:
            bold = not num.startswith("     ")
            if bold:
                self.set_font("Helvetica", "B", 10)
            else:
                self.set_font("Helvetica", "", 10)
            self.cell(0, 6, f"{num}  {title}")
            self.ln(6)

    # -- text primitives ----------------------------------------------------

    def h1(self, text):
        self.ln(4)
        self.set_font("Helvetica", "B", 16)
        self.set_fill_color(20, 40, 80)
        self.set_text_color(255, 255, 255)
        self.cell(0, 9, f"  {text}", fill=True)
        self.set_text_color(0, 0, 0)
        self.ln(6)

    def h2(self, text):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(20, 40, 80)
        self.cell(0, 7, text)
        self.set_text_color(0, 0, 0)
        self.set_draw_color(20, 40, 80)
        self.set_line_width(0.3)
        y = self.get_y()
        self.line(self.MARGIN, y, 210 - self.MARGIN, y)
        self.ln(5)

    def h3(self, text):
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(60, 80, 140)
        self.cell(0, 6, text)
        self.set_text_color(0, 0, 0)
        self.ln(5)

    def body(self, text):
        self.set_font("Helvetica", "", 9.5)
        self.multi_cell(self.BODY_W, 5, text)
        self.ln(2)

    def formula(self, text):
        self.ln(1)
        self.set_font("Courier", "", 9)
        self.set_fill_color(240, 242, 248)
        self.set_draw_color(200, 205, 220)
        self.set_line_width(0.2)
        self.multi_cell(self.BODY_W, 5, f"  {text}", border=1, fill=True)
        self.ln(2)
        self.set_draw_color(0, 0, 0)

    def code(self, text):
        self.ln(1)
        self.set_font("Courier", "", 8.5)
        self.set_fill_color(245, 245, 245)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.2)
        self.multi_cell(self.BODY_W, 4.5, text, border=1, fill=True)
        self.ln(2)
        self.set_draw_color(0, 0, 0)

    def bullet(self, items):
        self.set_font("Helvetica", "", 9.5)
        for item in items:
            self.cell(6, 5, chr(149))
            self.multi_cell(self.BODY_W - 6, 5, item)
        self.ln(1)

    def param_table(self, rows):
        """rows: list of (param, type, default, description)"""
        self.set_font("Helvetica", "B", 8.5)
        self.set_fill_color(230, 235, 248)
        self.set_draw_color(180, 185, 210)
        self.set_line_width(0.2)
        col_w = [42, 22, 22, 88]
        headers = ["Parameter", "Type", "Default", "Description"]
        for i, h in enumerate(headers):
            self.cell(col_w[i], 6, h, border=1, fill=True)
        self.ln()
        self.set_font("Helvetica", "", 8)
        fills = [False, True]
        for ri, (p, t, d, desc) in enumerate(rows):
            fill = fills[ri % 2]
            self.set_fill_color(248, 249, 253) if fill else self.set_fill_color(255, 255, 255)
            # Multi-line description requires special handling
            x0 = self.get_x()
            y0 = self.get_y()
            for i, (val, w) in enumerate(zip([p, t, d, desc], col_w)):
                self.multi_cell(w, 5, val, border=1, fill=fill)
                if i < len(col_w) - 1:
                    self.set_xy(x0 + sum(col_w[:i+1]), y0)
            self.ln()
        self.set_draw_color(0, 0, 0)
        self.ln(2)

    def note(self, text):
        self.ln(1)
        self.set_fill_color(255, 248, 225)
        self.set_draw_color(220, 180, 50)
        self.set_line_width(0.3)
        self.set_font("Helvetica", "I", 9)
        self.multi_cell(self.BODY_W, 5, f"  Note: {text}", border="L", fill=True)
        self.set_line_width(0.2)
        self.set_draw_color(0, 0, 0)
        self.ln(2)


# -- document sections ----------------------------------------------------------

def build_pdf():
    pdf = Doc()
    pdf.cover()
    pdf.toc_page()

    # -- 1. Overview --------------------------------------------------------
    pdf.add_page()
    pdf.h1("1.  Overview & Architecture")
    pdf.body(
        "The PAC Framework is a Python library and PyQt6 desktop application for synthesising "
        "realistic intracranial EEG (iEEG) signals with configurable neural oscillations, "
        "1/f background activity, line noise, and phase-amplitude coupling (PAC). "
        "Its primary purpose is to produce ground-truth-labelled synthetic datasets "
        "for benchmarking PAC analysis algorithms."
    )
    pdf.h2("Core design principles")
    pdf.bullet([
        "Immutable data model  -  Session, Channels, Events, Timeline are all frozen "
        "dataclasses. No in-place mutation anywhere in the scientific layer.",
        "GUI-free science layer  -  pac_framework.generator and pac_framework.core import "
        "zero Qt code. They can be used from notebooks, scripts, or test suites without "
        "a display.",
        "Deterministic reproducibility  -  all randomness is derived from a single master "
        "seed via BLAKE2b hashing. Given the same seed and config you always get the "
        "identical waveform.",
        "Ground-truth provenance  -  every synthetic session carries a ground_truth dict "
        "containing the pre-coupling carrier waveforms, instantaneous phases, chi "
        "trajectories, projection matrix, and the full SignalConfig JSON.",
        "Per-session signal config  -  each session in a subject can have its own "
        "independent population/coupling/projection configuration.",
    ])

    pdf.h2("File layout")
    pdf.code(
        "pac_framework/\n"
        "  __init__.py              Public API  -  import pac_framework as pac\n"
        "  core/\n"
        "    data_model.py          Timeline, Channels, Events, Session, Subject, Result\n"
        "    seed_util.py           derive(parent, *labels) -> int  (BLAKE2b)\n"
        "    manifest_migrations.py Schema version migration chain (0.0.0 -> 0.10.0)\n"
        "  generator/\n"
        "    config.py              All Pydantic frozen models (SignalConfig, etc.)\n"
        "    oscillator.py          synth_oscillator  -  band-limited noise AM model\n"
        "    bursts.py              burst_envelope  -  Poisson burst gating\n"
        "    background.py          synth_background  -  1/f spectral shaping\n"
        "    line_noise.py          synth_line_noise  -  deterministic harmonics\n"
        "    couplings.py           apply_phase_to_amplitude, build_window_envelope\n"
        "    pipeline.py            apply_couplings  -  topological ordering + PAC apply\n"
        "    projection.py          build_projection_matrix  -  population -> channel\n"
        "    scheduling.py          schedule_class_events  -  Poisson event scheduler\n"
        "    runner.py              build_sessions, generate_signals (public entry points)\n"
        "  gui/\n"
        "    main_window.py         MainWindow hub (toolbar, Build, Generate, Save, Load)\n"
        "    subject_state.py       SubjectState  -  GUI-only workspace state\n"
        "    tabs/\n"
        "      subject_designer.py  Tab 1  -  metadata, sessions, event catalogs, shafts\n"
        "      signal_config.py     Tab 2  -  populations, couplings, projection\n"
        "      data_browser.py      Tab 3  -  channel viewer, timeline preview\n"
        "    widgets/\n"
        "      oscillator_advanced_dialog.py  Advanced oscillator params dialog\n"
        "      coupling_modulation_dialog.py  Event modulation dialog\n"
        "      timeline_preview.py            Event raster / timeline widget\n"
        "      tracked_viewer.py              Multi-channel waveform viewer\n"
        "    persistence.py         save_subject / load_subject (HDF5 + JSON manifest)\n"
    )

    # -- 2. Pipeline --------------------------------------------------------
    pdf.add_page()
    pdf.h1("2.  The Signal Pipeline  -  Step by Step")
    pdf.body(
        "When you press Generate Signals (Ctrl+G) the following operations are executed "
        "sequentially for each session. All steps are pure NumPy/SciPy  -  no Qt is involved."
    )
    pdf.h3("Step 1  -  Seed derivation")
    pdf.body(
        "A deterministic seed tree is built from the master seed using BLAKE2b hashing:"
    )
    pdf.formula(
        "subject_seed  = derive(master_seed, 'subject', subject_name)\n"
        "session_seed  = derive(subject_seed, 'session', session_index)\n"
        "pop_seed      = derive(session_seed, 'population', population_id)\n"
        "channel_seed  = derive(session_seed, 'channel', channel_index)"
    )
    pdf.body(
        "Changing only the master seed regenerates every waveform independently; "
        "changing only a population ID changes only that population's seed branch."
    )
    pdf.h3("Step 2  -  Oscillator synthesis (per population)")
    pdf.body(
        "Each OscillatorPopulation is synthesised independently by synth_oscillator(). "
        "The result is an OscillatorOutput(carrier, phase) pair. "
        "See Section 3 for the full sub-pipeline."
    )
    pdf.h3("Step 3  -  Chi trajectory computation")
    pdf.body(
        "For each PhaseToAmpCoupling, a chi(t) time series is built. "
        "If no EventModulation entries exist, chi(t) is a constant array equal to c.chi. "
        "If event modulations are present, each event occurrence stamps a Tukey window "
        "of height (peak_chi - baseline_chi) into the trajectory, and multiple "
        "modulations are combined by elementwise maximum. See Section 6.2."
    )
    pdf.h3("Step 4  -  Coupling application (topological order)")
    pdf.body(
        "apply_couplings() sorts populations by Kahn's topological algorithm "
        "(driver before target), then for each PAC coupling applies the von Mises "
        "envelope to the target carrier using the driver's phase. See Section 6.1."
    )
    pdf.h3("Step 5  -  Population-to-channel projection")
    pdf.body(
        "The (n_populations x n_samples) carrier matrix X is left-multiplied by M.T "
        "to produce an (n_channels x n_samples) channel signal matrix. "
        "M is built by build_projection_matrix() from the channel layout. See Section 7."
    )
    pdf.formula("channel_signals = M.T  @  X      # (n_channels, n_samples)")
    pdf.h3("Step 6  -  Line noise addition")
    pdf.body(
        "All LineNoisePopulations are summed into a single trace and broadcast-added "
        "identically to every channel (apparatus-level noise)."
    )
    pdf.h3("Step 7  -  Background (1/f) addition")
    pdf.body(
        "All BackgroundPopulations are summed and broadcast-added identically across "
        "channels (shared neural background)."
    )
    pdf.h3("Step 8  -  Per-channel independent Gaussian noise")
    pdf.body(
        "Each channel receives independent Gaussian noise drawn from "
        "N(0, channel_noise_sd^2) using a channel-specific seed. "
        "This models electrode-level thermal/measurement noise."
    )
    pdf.h3("Step 9  -  Ground-truth bundle assembly")
    pdf.body(
        "All intermediate arrays (pre-coupling carriers, instantaneous phases, "
        "chi trajectories, line noise traces, background traces, projection matrix, "
        "population order, channel order, full SignalConfig JSON) are packed into "
        "session.ground_truth dict and stored with the session."
    )

    # -- 3. Oscillators -----------------------------------------------------
    pdf.add_page()
    pdf.h1("3.  Oscillator Populations")
    pdf.body(
        "An OscillatorPopulation is the primary neural signal source. "
        "Each population represents one neural group oscillating in a specific frequency band "
        "in a specific brain region. Multiple populations can coexist and be coupled."
    )
    pdf.h2("Core parameters")
    pdf.param_table([
        ("id",               "str",   "(required)", "Unique identifier used in couplings and ground truth."),
        ("center_frequency", "float", "(required)", "Center frequency in Hz (must be > 0)."),
        ("bandwidth",        "float", "(required)", "Bandwidth in Hz. 0 = pure sinusoid; > 0 = band-limited AM noise model."),
        ("amplitude",        "float", "(required)", "Output amplitude in uV (carrier.std() == amplitude after scaling)."),
        ("region",           "str",   "(required)", "Brain region label. Used by region_match projection to select channels."),
        ("seed_tag",         "str",   "'default'",  "Additional seed disambiguation tag (rarely needed unless duplicating configs)."),
    ])

    pdf.h2("The two carrier models")
    pdf.h3("bandwidth = 0: Pure sinusoid")
    pdf.body(
        "The carrier is a pure cosine at the center frequency, optionally with "
        "PAF drift applied to the instantaneous frequency:"
    )
    pdf.formula(
        "carrier(t) = sqrt(2) * cos(phase(t))\n"
        "phase(t)   = 2*pi * cumsum(f(t)) / sfreq\n"
        "f(t)       = center_frequency  (constant when sigma_hz=0)"
    )
    pdf.body(
        "With bandwidth=0 there is no RNG involved in the carrier itself "
        "(pure determinism), so every channel receiving this population gets an identical "
        "sinusoid before projection."
    )
    pdf.h3("bandwidth > 0: Band-limited AM noise model")
    pdf.body(
        "White Gaussian noise is low-pass filtered at cutoff = bandwidth/2, "
        "then amplitude-modulated by the cosine carrier. "
        "This produces a realistic oscillatory burst with natural amplitude variability:"
    )
    pdf.formula(
        "envelope(t) = lowpass_filter(white_noise, cutoff=bandwidth/2)\n"
        "carrier(t)  = envelope(t) * cos(phase(t))"
    )
    pdf.body(
        "The filter uses a 4th-order Butterworth applied with filtfilt (zero-phase). "
        "2 seconds of throwaway samples prefix the signal to absorb filter edge transients."
    )

    pdf.h2("3.1  Frequency Drift (PAF Drift)")
    pdf.body(
        "The peak alpha frequency (PAF) of real neural oscillations drifts slowly over time. "
        "PAFDrift models this as an Ornstein-Uhlenbeck (OU) process on the instantaneous "
        "frequency:"
    )
    pdf.formula(
        "f[n+1] = center + (f[n] - center) * exp(-dt/tau)\n"
        "       + sigma * sqrt(1 - exp(-2*dt/tau)) * z[n]\n"
        "where z[n] ~ N(0, 1), dt = 1/sfreq\n"
        "f[n] is clipped to >= 0.1 Hz"
    )
    pdf.param_table([
        ("sigma_hz",    "float", "0.0", "Standard deviation of frequency fluctuations in Hz. 0 = no drift (pure sinusoid at center_frequency)."),
        ("tau_seconds", "float", "5.0", "Correlation time of the OU process in seconds. Larger = slower, smoother drift."),
    ])
    pdf.note("PAF drift is active even with bandwidth=0. You can have a pure sinusoid with a slowly drifting frequency.")

    pdf.h2("3.2  Waveform Shape (Harmonic Injection)")
    pdf.body(
        "Real neural oscillations are not perfect sinusoids. "
        "WaveformShape injects controlled harmonics to produce sharp peaks, flat troughs, "
        "or rise/decay asymmetry  -  hallmarks of theta, alpha and slow oscillations:"
    )
    pdf.formula(
        "carrier += sharpness_harmonics:  0.3*|s|*cos(2*phase + phi) + 0.1*|s|*cos(4*phase + phi)\n"
        "                                 phi = 0 if s>0, pi if s<0\n"
        "carrier += asymmetry_harmonics:  0.2*|a|*cos(3*phase + phi) + 0.05*|a|*cos(5*phase + phi)\n"
        "                                 phi = pi/2 if a>0, -pi/2 if a<0"
    )
    pdf.param_table([
        ("peak_trough_sharpness", "float [-1,1]", "0.0", "Positive = sharper peaks, flatter troughs (like hippocampal theta). Negative = flatter peaks, sharper troughs."),
        ("rise_decay_asymmetry",  "float [-1,1]", "0.0", "Positive = fast rise, slow decay. Negative = slow rise, fast decay."),
    ])

    pdf.h2("3.3  Burst Mode")
    pdf.body(
        "By default oscillators are continuous. Setting mode='bursty' gates the "
        "carrier with a stochastic on/off envelope. Bursts are Poisson-distributed, "
        "with log-normal duration and raised-cosine tapering to avoid hard edges:"
    )
    pdf.param_table([
        ("mode",                  "str",   "'continuous'", "'continuous' or 'bursty'. Bursty gates the carrier with a stochastic envelope."),
        ("rate_hz",               "float", "0.5",          "Mean burst rate in Hz (bursts per second). Active only when mode='bursty'."),
        ("duration_cycles_mean",  "float", "3.0",          "Mean burst duration in carrier cycles."),
        ("duration_cycles_sd",    "float", "0.5",          "Standard deviation of burst duration. 0 = fixed length."),
        ("refractory_cycles",     "float", "1.0",          "Minimum gap between bursts in carrier cycles (refractory period)."),
    ])
    pdf.note(
        "Burst mode affects the entire recording  -  there is no window-alignment to events. "
        "To make bursting correlate with task events, combine burst mode with "
        "event-modulated coupling depth (Section 6.2) on a gamma population."
    )

    pdf.h2("3.4  Artifacts")
    pdf.body(
        "ArtifactConfig injects sharp-edge transient spikes into the carrier after "
        "amplitude scaling. This models electrode movement artifacts, "
        "saturation clipping, and similar contamination:"
    )
    pdf.param_table([
        ("rate_hz",        "float", "0.0", "Artifact injection rate in Hz. 0 = no artifacts."),
        ("amplitude_mult", "float", "3.0", "Spike amplitude as a multiple of the carrier's std. Default 3x gives salient but realistic artifacts."),
        ("width_samples",  "int",   "5",   "Width of each transient spike in samples. At 1000 Hz, 5 samples = 5 ms."),
    ])
    pdf.note("Artifact rate_hz=0 (default) produces no artifacts. Spikes are randomly positive or negative.")

    # -- 4. Background ------------------------------------------------------
    pdf.add_page()
    pdf.h1("4.  Background (1/f) Populations")
    pdf.body(
        "Real iEEG signals contain aperiodic 1/f-like background power that is not "
        "attributable to any specific oscillation. BackgroundPopulation models this "
        "via spectral shaping of white noise in the frequency domain:"
    )
    pdf.formula(
        "A(f) = 1 / sqrt(f^slope + knee_hz^slope)   (knee_hz > 0, Lorentzian form)\n"
        "A(f) = 1 / f^(slope/2)                      (knee_hz = 0, pure power law)\n"
        "DC component (f=0) is pinned to f=1 to avoid singularity."
    )
    pdf.body(
        "The output is normalised so std == amplitude (uV). "
        "Background is shared across all channels (broadcast)  -  it models "
        "a common neural background, not independent electrode noise."
    )
    pdf.param_table([
        ("id",        "str",   "(required)", "Unique identifier for this background population."),
        ("slope",     "float", "1.5",        "Spectral exponent. Typical iEEG: 1.0-2.5. Higher = more low-frequency dominated."),
        ("knee_hz",   "float", "0.0",        "Spectral knee in Hz. Above the knee the slope flattens. 0 = pure power law."),
        ("amplitude", "float", "1.0",        "Output amplitude in uV (std of the trace)."),
        ("seed_tag",  "str",   "'default'",  "Seed disambiguation tag."),
    ])

    # -- 5. Line Noise ------------------------------------------------------
    pdf.h1("5.  Line Noise Populations")
    pdf.body(
        "LineNoisePopulation produces a deterministic sum of sinusoids at a fundamental "
        "frequency and its harmonics, modelling electrical interference from power mains:"
    )
    pdf.formula(
        "trace(t) = SUM_k  amplitude_per_harmonic[k] * sqrt(2) * cos(2*pi * harmonics[k] * frequency * t)\n"
        "The sqrt(2) factor makes each harmonic's RMS = amplitude_per_harmonic[k]."
    )
    pdf.body(
        "Line noise is deterministic (no RNG) and is broadcast identically to all channels "
        "since mains interference is apparatus-level."
    )
    pdf.param_table([
        ("id",                    "str",         "(required)", "Unique identifier."),
        ("frequency",             "float",       "60.0",       "Fundamental frequency in Hz. 60 Hz (US/Japan) or 50 Hz (Europe)."),
        ("harmonics",             "list[int]",   "[1, 2, 3]",  "List of harmonic indices. [1,2,3] = fundamental + 2nd + 3rd harmonic."),
        ("amplitude_per_harmonic","list[float]", "[1.0,0.3,0.1]", "RMS amplitude in uV for each harmonic in the harmonics list."),
    ])

    # -- 6. Couplings -------------------------------------------------------
    pdf.add_page()
    pdf.h1("6.  Couplings")
    pdf.body(
        "Couplings define directional relationships between populations. "
        "They are validated against the population graph (no unknown IDs, no cycles) "
        "before synthesis. Multiple couplings can share drivers or targets."
    )

    pdf.h2("6.1  Phase-to-Amplitude Coupling (PAC)")
    pdf.body(
        "PAC is the core feature of the framework. The amplitude of a high-frequency "
        "population (the target) is modulated by the phase of a low-frequency population "
        "(the driver). This is the canonical theta-gamma PAC mechanism."
    )
    pdf.body("The modulation uses the von Mises kernel:")
    pdf.formula(
        "E(phi; chi, phi_0, kappa) = (1 - chi) + chi * exp(kappa * cos(phi - phi_0) - kappa)\n"
        "\n"
        "At phi = phi_0:      E = 1.0  (maximum  -  carrier amplitude unchanged)\n"
        "At phi = phi_0 + pi: E = (1-chi) + chi * exp(-2*kappa)  (minimum)\n"
        "chi = 0:             E = 1.0 everywhere (no modulation)\n"
        "kappa = 0:           E = 1.0 everywhere (no directional preference)"
    )
    pdf.body("The modulated carrier is:")
    pdf.formula("target_carrier_out(t) = target_carrier(t) * E(driver_phase(t))")
    pdf.param_table([
        ("driver",  "str",   "(required)", "Population ID of the phase driver (low-frequency oscillation)."),
        ("target",  "str",   "(required)", "Population ID of the amplitude target (high-frequency oscillation)."),
        ("chi",     "float [0,1]", "0.5", "Baseline coupling depth. 0 = no coupling, 1 = full coupling."),
        ("phi_0",   "float (rad)", "0.0", "Preferred coupling phase in radians. GUI shows degrees. phi_0=0 = coupling peaks at cosine peak of driver."),
        ("kappa",   "float >= 0",  "2.0", "Concentration parameter of the von Mises distribution. Higher = narrower coupling window."),
    ])
    pdf.note(
        "The driver's carrier amplitude is NOT modified  -  only the target is affected. "
        "The driver's instantaneous phase is always taken from the original synthesised "
        "phase (pre-coupling), regardless of any coupling chain."
    )

    pdf.h2("6.2  Event-Modulated Coupling Depth")
    pdf.body(
        "G5b allows the coupling depth chi(t) to vary over time, rising transiently "
        "after experimental events. This models task-locked PAC enhancement  -  "
        "e.g. theta-gamma coupling that increases following a memory encoding cue."
    )
    pdf.body("Each PhaseToAmpCoupling may carry a tuple of EventModulation entries:")
    pdf.formula(
        "lift_e(t) = (peak_chi_e - chi_baseline) * envelope_e(t)\n"
        "max_lift(t) = max over all e of lift_e(t)\n"
        "chi(t) = clip(chi_baseline + max_lift(t), 0, 1)\n"
        "\n"
        "envelope_e(t) is a Tukey (flat-topped raised-cosine) window:\n"
        "  - starts at latency_sec after each event onset\n"
        "  - total width = window_sec\n"
        "  - cosine ramps occupy edge_fraction of the total width on each side\n"
        "  - flat top is 1.0 (full lift to peak_chi)\n"
        "  - multiple onsets combined by elementwise maximum"
    )
    pdf.param_table([
        ("event_label",   "str",        "(required)", "Name of the event class that triggers this chi lift. Must match a class in the session's event catalog."),
        ("peak_chi",      "float [0,1]","(required)", "The chi value reached at the peak of the window (flat-top = 1.0 on the envelope * lift)."),
        ("window_sec",    "float > 0",  "(required)", "Total width of the Tukey window in seconds."),
        ("latency_sec",   "float >= 0", "0.0",        "Delay from event onset to start of window in seconds."),
        ("edge_fraction", "float [0,0.5]","0.25",     "Fraction of window_sec used for each raised-cosine ramp. 0 = rectangular, 0.5 = Hann window."),
    ])
    pdf.note(
        "If peak_chi < chi_baseline, the modulation produces a negative lift (chi dip). "
        "Multiple EventModulation entries on the same coupling are combined by max  -  "
        "the largest lift at each time point wins."
    )

    pdf.h2("6.3  Phase-to-Phase Coupling (PPC)")
    pdf.body(
        "PhaseToPhaseCoupling specifies a phase-locking relationship between two "
        "oscillations (n:m coupling). In the current implementation PPC edges are "
        "used for topological ordering only  -  no synthesis action is applied. "
        "Full PPC synthesis is planned for a future version."
    )
    pdf.param_table([
        ("driver",           "str",         "(required)", "Phase driver population ID."),
        ("target",           "str",         "(required)", "Phase target population ID."),
        ("coupling_strength","float [0,1]", "0.3",        "Reserved for future synthesis."),
        ("delay_ms",         "float >= 0",  "15.0",       "Phase lag in milliseconds. Reserved for future synthesis."),
        ("n_to_m_ratio",     "tuple[int,int]","(1, 1)",   "n:m frequency ratio (e.g. (4,1) for 4:1 theta:delta). Reserved."),
    ])

    # -- 7. Projection ------------------------------------------------------
    pdf.add_page()
    pdf.h1("7.  Population-to-Channel Projection")
    pdf.body(
        "The projection step maps each oscillator population to the physical electrode "
        "channels that record it. This is controlled by ProjectionConfig."
    )
    pdf.formula(
        "X shape: (n_populations, n_samples)    -  stacked carrier waveforms\n"
        "M shape: (n_populations, n_channels)   -  projection weight matrix\n"
        "channel_signals = M.T @ X              -  (n_channels, n_samples)"
    )
    pdf.h2("Projection modes")
    pdf.h3("region_match (default)")
    pdf.body(
        "Entry M[p, c] = 1.0 if population p's region matches channel c's region, "
        "else 0.0. This means a hippocampal oscillation only reaches hippocampal "
        "electrodes, and an amygdala oscillation only reaches amygdala electrodes. "
        "It is anatomy-aware but binary."
    )
    pdf.h3("all_identical")
    pdf.body(
        "Every entry M[p, c] = 1.0. All populations reach all channels identically. "
        "Useful for single-region simulations or when spatial separation is not needed."
    )
    pdf.param_table([
        ("mode",             "str",       "'region_match'", "'region_match' or 'all_identical'. Controls how oscillator populations map to channels."),
        ("channel_noise_sd", "float >= 0","3.0",            "Standard deviation of per-channel independent Gaussian noise (uV). Added after projection."),
    ])
    pdf.note(
        "Background (1/f) and line noise are NOT projected through M. "
        "They bypass projection and are broadcast identically to all channels."
    )

    # -- 8. Channel noise ---------------------------------------------------
    pdf.h1("8.  Per-Channel Independent Noise")
    pdf.body(
        "After projection, background addition, and line noise addition, each channel "
        "receives independent Gaussian noise from its own deterministic seed:"
    )
    pdf.formula(
        "channel_seed = derive(session_seed, 'channel', channel_index)\n"
        "rng = np.random.default_rng(channel_seed)\n"
        "channel_data[j] = channel_signals[j] + rng.normal(0, channel_noise_sd, n_samples)"
    )
    pdf.body(
        "This models electrode-level measurement noise, thermal noise, and "
        "impedance differences. Set channel_noise_sd=0 to disable per-channel noise "
        "entirely (useful for isolated testing of coupling properties)."
    )

    # -- 9. Ground Truth ----------------------------------------------------
    pdf.add_page()
    pdf.h1("9.  Ground-Truth Bundle")
    pdf.body(
        "Every synthetic session carries a ground_truth dict with full provenance. "
        "This is what separates PAC Framework from generic signal simulators  -  "
        "you always know the exact true chi(t) trajectory, phases, and waveforms."
    )
    pdf.param_table([
        ("pre_coupling_carriers", "dict[str, ndarray]", "", "Carrier waveform for each oscillator population, BEFORE any coupling was applied. Shape (n_samples,)."),
        ("phases",                "dict[str, ndarray]", "", "Instantaneous phase (wrapped to [-pi, pi]) for each oscillator population. Shape (n_samples,)."),
        ("chi_trajectories",      "dict[str, ndarray]", "", "True chi(t) time series for each PAC coupling, keyed as 'driver__to__target'. Constant if no EventModulation, time-varying if modulated. Shape (n_samples,)."),
        ("line_noise",            "dict[str, ndarray]", "", "Line noise trace for each LineNoisePopulation. Shape (n_samples,)."),
        ("backgrounds",           "dict[str, ndarray]", "", "1/f background trace for each BackgroundPopulation. Shape (n_samples,)."),
        ("projection_matrix",     "ndarray",            "", "The (n_populations, n_channels) projection weight matrix M used to map carriers to channels."),
        ("oscillator_order",      "list[str]",          "", "Ordered list of oscillator population IDs matching the row order of the projection matrix and pre_coupling_carriers."),
        ("channel_order",         "list[str]",          "", "Ordered list of channel names matching the column order of the projection matrix."),
        ("signal_config_json",    "str",                "", "Full JSON serialisation of the SignalConfig used for this session. Enables exact replay."),
    ])
    pdf.body("Example access:")
    pdf.code(
        "session = sessions[0]\n"
        "gt = session.ground_truth\n"
        "\n"
        "# True chi trajectory for theta->gamma coupling\n"
        "chi_t = gt['chi_trajectories']['theta__to__gamma']   # shape (n_samples,)\n"
        "\n"
        "# Pre-coupling theta carrier\n"
        "theta_pre = gt['pre_coupling_carriers']['theta']      # shape (n_samples,)\n"
        "\n"
        "# Theta instantaneous phase\n"
        "theta_phase = gt['phases']['theta']                   # shape (n_samples,)\n"
        "\n"
        "# Which channels received theta?\n"
        "M = gt['projection_matrix']                          # (n_pops, n_channels)\n"
        "theta_idx = gt['oscillator_order'].index('theta')\n"
        "theta_channels = [gt['channel_order'][c] for c, w in enumerate(M[theta_idx]) if w > 0]"
    )

    # -- 10. Experiment Design ----------------------------------------------
    pdf.add_page()
    pdf.h1("10.  Experiment Design  -  Sessions & Events")
    pdf.body(
        "Before synthesising signals you build a skeleton of sessions with scheduled "
        "events using build_sessions(). This separates experimental design "
        "(what happened and when) from signal physics (what the neural signal looks like)."
    )
    pdf.h2("SessionSpec")
    pdf.param_table([
        ("date",          "str",                "(required)", "ISO date string for the recording (e.g. '2026-01-15')."),
        ("duration_sec",  "float > 0",          "(required)", "Session duration in seconds."),
        ("task",          "str",                "'synthetic'","Free-form task label stored in Session.task."),
        ("event_catalog", "tuple[EventClass,]", "()",         "All event classes for this session. Each class is scheduled independently."),
    ])
    pdf.h2("EventClass")
    pdf.body(
        "Defines one class of experimental events. Onsets are sampled from a Poisson "
        "process and then filtered by a minimum inter-event gap:"
    )
    pdf.param_table([
        ("name",        "str",       "(required)", "Event class label (e.g. 'cue_onset', 'response')."),
        ("rate_hz",     "float > 0", "(required)", "Expected events per second (Poisson rate)."),
        ("min_gap_sec", "float >= 0","0.0",        "Minimum inter-event interval in seconds. Greedy forward walk drops events too close together."),
    ])
    pdf.body(
        "Each EventClass gets its own deterministic seed derived from the session seed. "
        "Multiple event classes are scheduled independently and then merged and sorted "
        "by time into a single Events object."
    )
    pdf.h2("Event scheduling algorithm")
    pdf.formula(
        "n = Poisson(rate_hz * duration_sec)\n"
        "candidates = sorted(Uniform(0, duration_sec), size=n)\n"
        "accepted = greedy forward walk: accept t if t - last_accepted >= min_gap_sec"
    )
    pdf.note(
        "The Poisson count draw means the actual number of events is random around the "
        "expected count. Use rate_hz=0.5 to get roughly 1 event per 2 seconds on average "
        "in a 60-second session (expected ~30 events, Poisson-distributed)."
    )

    # -- 11. GUI ------------------------------------------------------------
    pdf.add_page()
    pdf.h1("11.  Using the GUI  -  Tab by Tab")
    pdf.body(
        "Launch the GUI by running: python -m pac_framework  (or the desktop shortcut). "
        "The window has three tabs and four toolbar buttons. "
        "The workflow is: configure in Tab 1 -> press Build -> configure in Tab 2 -> "
        "press Generate -> inspect in Tab 3 -> Save."
    )
    pdf.h2("Toolbar buttons")
    pdf.param_table([
        ("Build Timeline & Events (Ctrl+B)", "", "", "Validates all config, calls build_sessions(), creates zero-filled channels with scheduled events. Must be done before Generate."),
        ("Generate Signals (Ctrl+G)",         "", "", "Calls generate_signals() on the current state. Switches to the Data Browser tab when done."),
        ("Save (Ctrl+S)",                     "", "", "Saves the subject to subjects/<name>/ as HDF5 session files + manifest.json."),
        ("Load (Ctrl+L)",                     "", "", "Opens a folder picker to load a previously saved subject directory."),
    ])

    pdf.h2("11.1  Subject Designer Tab")
    pdf.body(
        "This tab defines WHO the subject is and WHAT happened in each session. "
        "It does not define the neural signals  -  that is Tab 2."
    )
    pdf.h3("Subject Metadata group")
    pdf.bullet([
        "Subject Name: arbitrary string identifier stored in Session.subject_id.",
        "Master Seed: integer seed for the entire deterministic synthesis chain.",
        "Sample Rate (Hz): sampling frequency shared across all sessions.",
        "Notes: free-text field (up to 1000 chars) for experimental notes.",
    ])
    pdf.h3("Sessions group")
    pdf.body(
        "Each row defines one recording session. Right-click or use the Add/Remove buttons. "
        "Columns: Date (ISO format), Duration (seconds), Task (label string). "
        "The 'Edit Catalog' button opens the per-session event catalog editor."
    )
    pdf.h3("Event Catalog editor")
    pdf.body(
        "Each session has its own event catalog. Default catalog contains three classes: "
        "cue_onset, decision_made, outcome  -  each at 0.2 Hz with 3s minimum gap. "
        "Edit columns: Class Name, Rate (Hz), Min Gap (s). "
        "Class names must be unique within a session. "
        "Any class name you define here becomes available as an event trigger "
        "in the Coupling Modulation dialog (Section 6.2)."
    )
    pdf.h3("Channel Layout group")
    pdf.body(
        "Defines the electrode geometry. Each row is one shaft (electrode array): "
        "Shaft (name, e.g. 'LA'), Region (e.g. 'amygdala'), Contacts (integer count), "
        "Spacing (mm between adjacent contacts). Channel names are auto-generated as "
        "ShaftName_ContactIndex (e.g. LA_00, LA_01, ..., LA_07). "
        "The region label must match the region string of oscillator populations "
        "for region_match projection to work."
    )

    pdf.h2("11.2  Signal Config Tab")
    pdf.body(
        "This tab defines the neural signal model for the currently selected session. "
        "The session selector at the top lets you switch between sessions; "
        "changes are stored per-session. "
        "The 'Apply to All Sessions' button copies the current config to every session."
    )
    pdf.h3("Oscillators group")
    pdf.body(
        "Each row is one OscillatorPopulation. Required columns: "
        "ID (unique), Center Freq (Hz), Bandwidth (Hz), Amplitude (uV), Region. "
        "The 'Advanced' button opens a dialog for WaveformShape, PAFDrift, BurstConfig, "
        "and ArtifactConfig parameters."
    )
    pdf.h3("Advanced Oscillator Dialog")
    pdf.body("Grouped into four sections:")
    pdf.bullet([
        "Waveform Shape: Peak/trough sharpness [-1,1] and Rise/decay asymmetry [-1,1].",
        "PAF Drift: sigma (Hz) and tau (seconds) for the OU frequency drift process.",
        "Burst Config: mode (continuous/bursty), rate (Hz), duration mean/SD (cycles), refractory (cycles).",
        "Artifacts: rate (Hz), amplitude multiplier, width (samples).",
    ])
    pdf.h3("Backgrounds (1/f) group")
    pdf.body(
        "Each row is one BackgroundPopulation. Columns: ID, Slope (exponent), Knee (Hz), Amplitude (uV)."
    )
    pdf.h3("Line Noise group")
    pdf.body(
        "Each row is one LineNoisePopulation. Columns: ID, Frequency (Hz), "
        "Harmonics (comma-separated integers), Amplitudes (comma-separated uV values). "
        "Example: harmonics='1,2,3', amplitudes='1.0,0.3,0.1' gives 60+120+180 Hz at those amplitudes."
    )
    pdf.h3("Couplings group  -  PAC table")
    pdf.body(
        "Each row defines one PhaseToAmpCoupling. Columns: "
        "Driver (oscillator ID dropdown), Target (oscillator ID dropdown), "
        "chi (baseline coupling depth), phi_0 in degrees, kappa. "
        "The 'Modulation...' button opens the Event Modulation dialog."
    )
    pdf.h3("Event Modulation Dialog")
    pdf.body(
        "Accessible via the 'Modulation...' button on each PAC coupling row. "
        "Each row in this dialog is one EventModulation entry. Columns: "
        "Event label (dropdown of the current session's event catalog), "
        "Peak chi [0,1], Window (s), Latency (s), Edge fraction [0,0.5]. "
        "Add/Remove rows with the buttons. Multiple rows combine by max at synthesis time."
    )
    pdf.h3("Couplings group  -  PPC table")
    pdf.body(
        "Each row defines one PhaseToPhaseCoupling. "
        "Columns: Driver, Target, Strength, Delay (ms), N:M ratio. "
        "PPC currently imposes ordering constraints only  -  no synthesis action."
    )
    pdf.h3("Projection group")
    pdf.body(
        "Mode dropdown: 'region_match' (default) or 'all_identical'. "
        "Channel Noise SD: Gaussian noise standard deviation in uV added independently "
        "to each channel after projection."
    )

    pdf.h2("11.3  Data Browser Tab")
    pdf.body(
        "Displays the generated waveforms. Shows one session at a time. "
        "All channels are displayed in a scrollable multi-trace viewer. "
        "Before Generate Signals is pressed, channels show flat zero. "
        "The timeline preview at the bottom shows the event raster "
        "(one row per event class, dots at onset times)."
    )
    pdf.note(
        "The Data Browser view is refreshed automatically after Generate Signals "
        "and after Load. Editing any parameter in Tab 1 or Tab 2 after generating "
        "signals will zero out the channel data with the message 'Signals invalidated'."
    )

    # -- 12. Programmatic API -----------------------------------------------
    pdf.add_page()
    pdf.h1("12.  Programmatic API (no GUI)")
    pdf.body(
        "The entire synthesis pipeline can be used from Python without launching the GUI. "
        "Import pac_framework as pac and use the public functions directly."
    )
    pdf.code(
        "import pac_framework as pac\n"
        "\n"
        "# 1. Define electrode layout\n"
        "channel_info = pac.channel_info_from_shafts([\n"
        "    {'shaft': 'LA', 'region': 'amygdala',    'contacts': 8, 'spacing_mm': 1.5},\n"
        "    {'shaft': 'LH', 'region': 'hippocampus', 'contacts': 8, 'spacing_mm': 1.5},\n"
        "])\n"
        "\n"
        "# 2. Define sessions\n"
        "specs = [\n"
        "    pac.SessionSpec(\n"
        "        date='2026-01-01', duration_sec=120.0, task='memory_task',\n"
        "        event_catalog=(\n"
        "            pac.EventClass(name='cue_onset', rate_hz=0.5, min_gap_sec=2.0),\n"
        "            pac.EventClass(name='response',  rate_hz=0.4, min_gap_sec=1.5),\n"
        "        ),\n"
        "    ),\n"
        "]\n"
        "\n"
        "# 3. Build skeleton sessions (zero channels + events)\n"
        "sessions = pac.build_sessions(\n"
        "    subject_name='sub-01', seed=42, sfreq=1000.0,\n"
        "    session_specs=specs, channel_info=channel_info,\n"
        ")\n"
        "\n"
        "# 4. Configure signals\n"
        "theta = pac.OscillatorPopulation(\n"
        "    id='theta', center_frequency=6.0, bandwidth=2.0,\n"
        "    amplitude=50.0, region='hippocampus',\n"
        "    burst=pac.BurstConfig(mode='continuous'),\n"
        "    paf_drift=pac.PAFDrift(sigma_hz=0.5, tau_seconds=8.0),\n"
        ")\n"
        "gamma = pac.OscillatorPopulation(\n"
        "    id='gamma', center_frequency=70.0, bandwidth=10.0,\n"
        "    amplitude=10.0, region='hippocampus',\n"
        "    burst=pac.BurstConfig(mode='bursty', rate_hz=1.5),\n"
        ")\n"
        "config = pac.SignalConfig(\n"
        "    populations=[theta, gamma],\n"
        "    couplings=[\n"
        "        pac.PhaseToAmpCoupling(\n"
        "            driver='theta', target='gamma',\n"
        "            chi=0.3, phi_0=0.0, kappa=3.0,\n"
        "            event_modulations=(\n"
        "                pac.EventModulation(\n"
        "                    event_label='cue_onset', peak_chi=0.85,\n"
        "                    window_sec=1.5, latency_sec=0.1, edge_fraction=0.25,\n"
        "                ),\n"
        "            ),\n"
        "        ),\n"
        "    ],\n"
        "    projection=pac.ProjectionConfig(mode='region_match', channel_noise_sd=3.0),\n"
        ")\n"
        "\n"
        "# 5. Synthesise\n"
        "sessions = pac.generate_signals(\n"
        "    sessions=sessions, signal_configs=[config],\n"
        "    master_seed=42, subject_name='sub-01',\n"
        ")\n"
        "\n"
        "# 6. Access data\n"
        "raw   = sessions[0].channels.data          # (n_channels, n_samples)\n"
        "times = sessions[0].timeline.times()        # (n_samples,) in seconds\n"
        "chi_t = sessions[0].ground_truth['chi_trajectories']['theta__to__gamma']\n"
        "hpc   = sessions[0].channels.get_channels(region='hippocampus')"
    )

    # -- 13. Saving / Loading -----------------------------------------------
    pdf.add_page()
    pdf.h1("13.  Saving & Loading Subjects")
    pdf.body(
        "The Save action writes to subjects/<subject_name>/ with one HDF5 file per session "
        "plus a JSON manifest. This structure can be reloaded by the GUI or by code."
    )
    pdf.h2("On-disk structure")
    pdf.code(
        "subjects/\n"
        "  sub-01/\n"
        "    manifest.json             Schema version + gui_config + supplementary config\n"
        "    session_000.h5            HDF5 for session 0 (channels, events, ground truth)\n"
        "    session_001.h5            HDF5 for session 1\n"
        "    ..."
    )
    pdf.h2("HDF5 session file layout")
    pdf.code(
        "session_000.h5\n"
        "  /identity               subject_id, session_id, task, date_recorded, origin\n"
        "  /timeline               sfreq, n_samples, tmin\n"
        "  /channels/data          (n_channels, n_samples) float64, gzip compressed\n"
        "  /channels/info/         per-column datasets: name, type, shaft, region, ...\n"
        "  /events/samples         int64 onset indices\n"
        "  /events/labels          UTF-8 encoded strings\n"
        "  /events/codes           int64 numeric codes\n"
        "  /ground_truth/pre_coupling_carriers/<pop_id>   float64\n"
        "  /ground_truth/phases/<pop_id>                  float64\n"
        "  /ground_truth/chi_trajectories/<coupling_key>  float64\n"
        "  /ground_truth/backgrounds/<pop_id>             float64\n"
        "  /ground_truth/line_noise/<pop_id>              float64\n"
        "  /ground_truth/projection_matrix               (n_pop, n_ch) float64"
    )
    pdf.h2("Schema version migration")
    pdf.body(
        "The manifest carries a schema_version field. When loading an older file the "
        "migration chain automatically updates it to the current version (0.10.0). "
        "The following migrations are applied in sequence:"
    )
    pdf.param_table([
        ("0.0.0 -> 0.1.0", "", "", "Add channel_layout to gui_config."),
        ("0.1.0 -> 0.2.0", "", "", "Add event_catalog to gui_config."),
        ("0.2.0 -> 0.3.0", "", "", "Add trial_structure to gui_config."),
        ("0.3.0 -> 0.4.0", "", "", "Restructure flat gui_config keys into nested sub-dicts; add subject metadata."),
        ("0.4.0 -> 0.5.0", "", "", "Expand uniform sessions spec into per-session row list; move sfreq to top level."),
        ("0.5.0 -> 0.6.0", "", "", "Move subject-level event_catalog into each session row."),
        ("0.6.0 -> 0.7.0", "", "", "Add signals_populated flag and default signal_config."),
        ("0.7.0 -> 0.8.0", "", "", "Replace single signal_config with per-session list session_signal_configs."),
        ("0.8.0 -> 0.9.0", "", "", "Add ArtifactConfig defaults to every oscillator population."),
        ("0.9.0 -> 0.10.0","", "", "Add event_modulations: [] to every PAC coupling entry."),
    ])

    # -- 14. Reproducibility ------------------------------------------------
    pdf.add_page()
    pdf.h1("14.  Deterministic Reproducibility")
    pdf.body(
        "All randomness in the framework is derived from a single master seed. "
        "The seed derivation uses BLAKE2b hashing to produce non-overlapping, "
        "uncorrelated sub-seeds for every stochastic component."
    )
    pdf.formula(
        "derive(parent_seed: int, *labels: str | int) -> int\n"
        "\n"
        "Encodes: struct.pack('>q', parent_seed) + ':'.join(str(l) for l in labels).encode()\n"
        "Returns: int.from_bytes(blake2b(encoded, digest_size=8).digest(), 'big')"
    )
    pdf.body("The seed tree looks like:")
    pdf.code(
        "master_seed (42)\n"
        "  derive('subject', 'sub-01')  -> subject_seed\n"
        "    derive('session', 0)       -> session_0_seed\n"
        "      derive('population', 'theta')  -> theta_seed\n"
        "        derive('paf_drift')          -> paf_seed      (theta OU drift)\n"
        "        derive('burst')              -> burst_seed     (theta burst envelope)\n"
        "        derive('artifact')           -> artifact_seed  (theta artifacts)\n"
        "      derive('population', 'gamma')  -> gamma_seed\n"
        "      derive('channel', 0)           -> channel_0_seed (per-channel noise)\n"
        "      derive('channel', 1)           -> channel_1_seed\n"
        "      derive('events', 'cue_onset')  -> event_seed     (event scheduling)\n"
        "    derive('session', 1)       -> session_1_seed\n"
        "      ..."
    )
    pdf.body(
        "Changing the master seed changes ALL waveforms. "
        "Changing a population's id changes only that population's branch. "
        "Adding a new session changes only that session's branch (existing sessions unaffected). "
        "This means you can create multiple independent realisations of the same experiment "
        "by just incrementing the master seed."
    )

    # -- 15. Parameter Quick Reference -------------------------------------
    pdf.add_page()
    pdf.h1("15.  Parameter Quick Reference")

    pdf.h2("SignalConfig")
    pdf.param_table([
        ("populations", "list[Population]", "[]",    "List of OscillatorPopulation, BackgroundPopulation, LineNoisePopulation."),
        ("couplings",   "list[Coupling]",   "[]",    "List of PhaseToAmpCoupling, PhaseToPhaseCoupling."),
        ("projection",  "ProjectionConfig", "default","Projection mode and per-channel noise level."),
    ])

    pdf.h2("OscillatorPopulation  -  full parameter list")
    pdf.param_table([
        ("id",                     "str",   "required",  "Unique population identifier."),
        ("center_frequency",       "float > 0","required","Center frequency in Hz."),
        ("bandwidth",              "float >= 0","required","Bandwidth in Hz. 0 = pure sine."),
        ("amplitude",              "float > 0","required","Output amplitude in uV (sets carrier std)."),
        ("region",                 "str",   "required",  "Brain region, must match channel layout for region_match projection."),
        ("waveform_shape.peak_trough_sharpness","float [-1,1]","0.0","Harmonic sharpness."),
        ("waveform_shape.rise_decay_asymmetry", "float [-1,1]","0.0","Harmonic asymmetry."),
        ("paf_drift.sigma_hz",     "float >= 0","0.0",   "OU frequency drift magnitude."),
        ("paf_drift.tau_seconds",  "float > 0", "5.0",   "OU frequency drift correlation time."),
        ("burst.mode",             "str",   "'continuous'","'continuous' or 'bursty'."),
        ("burst.rate_hz",          "float > 0","0.5",    "Burst rate in Hz."),
        ("burst.duration_cycles_mean","float > 0","3.0", "Mean burst duration in carrier cycles."),
        ("burst.duration_cycles_sd",  "float >= 0","0.5","Burst duration SD in carrier cycles."),
        ("burst.refractory_cycles",   "float >= 0","1.0","Refractory period in carrier cycles."),
        ("artifact.rate_hz",       "float >= 0","0.0",   "Artifact injection rate. 0 = disabled."),
        ("artifact.amplitude_mult","float > 0", "3.0",   "Artifact amplitude as carrier std multiple."),
        ("artifact.width_samples", "int > 0",   "5",     "Artifact transient width in samples."),
    ])

    pdf.h2("PhaseToAmpCoupling  -  full parameter list")
    pdf.param_table([
        ("driver",   "str",         "required", "Driver population ID (phase source)."),
        ("target",   "str",         "required", "Target population ID (amplitude modulated)."),
        ("chi",      "float [0,1]", "0.5",      "Baseline coupling depth."),
        ("phi_0",    "float (rad)", "0.0",       "Preferred phase in radians (GUI uses degrees)."),
        ("kappa",    "float >= 0",  "2.0",       "Von Mises concentration (coupling sharpness)."),
        ("event_modulations[*].event_label",   "str",          "required","Session event class that triggers this lift."),
        ("event_modulations[*].peak_chi",      "float [0,1]",  "required","Chi value reached at window peak."),
        ("event_modulations[*].window_sec",    "float > 0",    "required","Tukey window total duration in seconds."),
        ("event_modulations[*].latency_sec",   "float >= 0",   "0.0",    "Delay from event onset to window start."),
        ("event_modulations[*].edge_fraction", "float [0,0.5]","0.25",   "Cosine ramp fraction (0=rectangular, 0.5=Hann)."),
    ])

    pdf.h2("BackgroundPopulation  -  full parameter list")
    pdf.param_table([
        ("id",        "str",       "required", "Unique identifier."),
        ("slope",     "float > 0", "1.5",      "1/f spectral exponent."),
        ("knee_hz",   "float >= 0","0.0",      "Spectral knee in Hz. 0 = pure power law."),
        ("amplitude", "float > 0", "1.0",      "Output amplitude in uV."),
    ])

    pdf.h2("LineNoisePopulation  -  full parameter list")
    pdf.param_table([
        ("id",                    "str",         "required",     "Unique identifier."),
        ("frequency",             "float > 0",   "60.0",         "Fundamental frequency in Hz."),
        ("harmonics",             "list[int]",   "[1, 2, 3]",    "Harmonic indices (1 = fundamental)."),
        ("amplitude_per_harmonic","list[float]", "[1.0,0.3,0.1]","RMS amplitude per harmonic in uV."),
    ])

    return pdf


if __name__ == "__main__":
    pdf = build_pdf()
    out = "/Users/qaryuti/Desktop/EEG Analysis Project/PAC_Framework_Signal_Generation_Reference.pdf"
    pdf.output(out)
    print(f"Written: {out}")
