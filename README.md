# pacgen

[![Tests](https://github.com/adhamq/pac-framework/actions/workflows/tests.yml/badge.svg)](https://github.com/adhamq/pac-framework/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A synthetic intracranial EEG generator built for benchmarking phase-amplitude coupling metrics.

---

## What it is and why it exists

PAC analysis — measuring how the amplitude of a high-frequency signal (say, gamma) is modulated by the phase of a low-frequency one (say, theta) — is messy to evaluate. The metrics most commonly used (modulation index, mean vector length, GLM-CFC, PLV, ρ_sin) make different assumptions and disagree in ways that are hard to interpret when you don't know the ground truth.

The idea behind pacgen is to turn Niebur's attention-as-synchrony framework into a parameter you can dial. You describe the oscillations you want, the coupling strength you want, and the event structure of your experiment, and pacgen hands you back a synthetic iEEG recording where the true chi(t) — the coupling depth at every millisecond — is known exactly. Then you run your metrics against it.

This is a phenomenological generator, not a biophysical model. It doesn't simulate neurons or synapses; it synthesises plausible signals with the statistical properties you'd expect from real iEEG: band-limited noise carriers, 1/f aperiodic background, 60 Hz line noise, PAF drift, burst structure, and optional transient artifacts. The goal is controlled ground truth, not biological realism.

Paper in preparation, Sampson lab, Johns Hopkins University.

---

## Install

```bash
# From PyPI (once published)
pip install pacgen

# From source
git clone https://github.com/adhamq/pac-framework.git
cd pac-framework
pip install -e ".[dev]"
```

Or if you just want to run it without editing:

```bash
pip install -r requirements.txt
pip install -e .
```

---

## Run the app

```bash
python -m pac_framework
```

Or if you installed via pip:

```bash
pacgen
```

The GUI has three tabs. In **Subject Designer** you define who the subject is, how long each session runs, what events get scheduled, and which brain regions have electrodes. In **Signal Config** you add oscillator populations, set coupling parameters, and — if you want task-locked PAC — configure per-coupling event modulations. In **Data Browser** you see the generated waveforms and event raster. Hit Save and it writes HDF5 session files plus a JSON manifest.

---

## Python API

If you'd rather script it:

```python
import pac_framework as pac

channel_info = pac.channel_info_from_shafts([
    {"shaft": "LH", "region": "hippocampus", "contacts": 8, "spacing_mm": 1.5},
])

spec = pac.SessionSpec(
    date="2026-01-01",
    duration_sec=120.0,
    task="memory_task",
    event_catalog=(
        pac.EventClass(name="cue_onset", rate_hz=0.5, min_gap_sec=2.0),
    ),
)

sessions = pac.build_sessions(
    subject_name="sub-01", seed=42, sfreq=1000.0,
    session_specs=[spec], channel_info=channel_info,
)

theta = pac.OscillatorPopulation(
    id="theta", center_frequency=6.0, bandwidth=2.0,
    amplitude=50.0, region="hippocampus",
)
gamma = pac.OscillatorPopulation(
    id="gamma", center_frequency=70.0, bandwidth=10.0,
    amplitude=10.0, region="hippocampus",
)

config = pac.SignalConfig(
    populations=[theta, gamma],
    couplings=[
        pac.PhaseToAmpCoupling(
            driver="theta", target="gamma",
            chi=0.2, kappa=3.0,
            # coupling depth rises to 0.8 for 1.5 s after each cue
            event_modulations=(
                pac.EventModulation(
                    event_label="cue_onset",
                    peak_chi=0.8, window_sec=1.5,
                ),
            ),
        ),
    ],
)

sessions = pac.generate_signals(
    sessions=sessions, signal_configs=[config],
    master_seed=42, subject_name="sub-01",
)

# ground truth is always there
chi_t = sessions[0].ground_truth["chi_trajectories"]["theta__to__gamma"]
raw   = sessions[0].channels.data  # (n_channels, n_samples)
```

See `examples/quickstart.py` for a more complete example with background noise, saving, and summaries.

---

## Folder layout

```
pac_framework/
  __init__.py          public API
  __main__.py          entry point for python -m pac_framework
  core/
    data_model.py      Session, Channels, Events, Timeline — the immutable data types
    seed_util.py       BLAKE2b seed derivation (everything is reproducible from one int)
    manifest_migrations.py  handles loading saves from older versions
  generator/
    config.py          all the Pydantic config models (SignalConfig, OscillatorPopulation, …)
    oscillator.py      the actual waveform synthesis: AM noise model, PAF drift, bursts, artifacts
    couplings.py       von Mises PAC kernel; Tukey window for event-modulated chi
    pipeline.py        topological sort + coupling application
    background.py      1/f spectral shaping
    line_noise.py      deterministic harmonic sum
    projection.py      population-to-channel mapping
    runner.py          build_sessions() and generate_signals() — the public entry points
  gui/
    main_window.py     the Qt window; thin hub that wires the three tabs together
    tabs/              Subject Designer, Signal Config, Data Browser
    widgets/           advanced dialogs, waveform viewer, event raster
    persistence.py     save/load (HDF5 + JSON manifest)
  tests/               172 tests, all science layer, no Qt dependencies
examples/
  quickstart.py        end-to-end example
docs/
  PAC_Framework_Signal_Generation_Reference.pdf
```

---

## Where it's at

The generator is complete for the metrics the paper needs: scalar PAC, event-modulated PAC (task-locked coupling depth), 1/f background, line noise, burst structure, PAF drift, waveform shape harmonics, and transient artifacts. Everything produces deterministic output from a single master seed.

The benchmarking pipeline — running MI, MVL, GLM-CFC, PLV, and ρ_sin against the generated signals — is in active development and not in this repo yet.

Phase-to-phase coupling (PPC) is stubbed in the schema and GUI but not synthesised yet.

---

## Development

```bash
pytest               # run all 172 tests
ruff check pac_framework/
python docs/generate_pdf.py   # rebuild the reference PDF (needs fpdf2)
```

---

## License

[MIT](LICENSE) — see LICENSE file for details.
