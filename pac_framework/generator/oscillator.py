"""Oscillator synthesis: band-limited AM noise, pure sinusoid, PAF drift."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy import signal as sp_signal

from pac_framework.core.seed_util import derive
from pac_framework.generator.config import OscillatorPopulation
from pac_framework.generator.bursts import burst_envelope
from pac_framework.generator.scheduling import schedule_class_events

logger = logging.getLogger(__name__)


@dataclass
class OscillatorOutput:
    """Carrier signal, instantaneous phase, and sub-seeds from synth_oscillator."""

    carrier: np.ndarray          # (n_samples,) float64, std == pop.amplitude
    phase: np.ndarray            # (n_samples,) float64, wrapped to [-π, π]
    internal_seeds: dict = field(default_factory=dict)  # keyed by feature tag


# ── private helpers ────────────────────────────────────────────────────────


def _ou_frequency_trajectory(
    center_hz: float,
    sigma_hz: float,
    tau_seconds: float,
    n_samples: int,
    sfreq: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Exact OU discretisation for instantaneous frequency.

    f[n+1] = center + (f[n] - center) * exp(-dt/tau)
             + sigma * sqrt(1 - exp(-2*dt/tau)) * z[n]

    Clamped to >= 0.1 Hz to prevent phase from ever decreasing.
    """
    dt = 1.0 / sfreq
    decay = np.exp(-dt / tau_seconds)
    noise_scale = sigma_hz * np.sqrt(1.0 - np.exp(-2.0 * dt / tau_seconds))

    innovations = rng.standard_normal(n_samples)
    f_t = np.empty(n_samples, dtype=np.float64)
    f_t[0] = center_hz
    for k in range(1, n_samples):
        f_t[k] = center_hz + (f_t[k - 1] - center_hz) * decay + noise_scale * innovations[k]
    np.clip(f_t, 0.1, None, out=f_t)
    return f_t


def _harmonic_coefficients(
    sharpness: float,
    asymmetry: float,
) -> list[tuple[int, float, float]]:
    """Return list of (harmonic_index, amplitude_scale, phase_offset).

    Coefficients scaled so that |parameter| == 1 gives harmonic amplitudes
    that are visibly non-sinusoidal without destroying the band-limited
    interpretation.

    sharpness controls even harmonics (2nd, 4th) — peak/trough asymmetry.
    asymmetry controls odd harmonics (3rd, 5th) — rise/decay asymmetry.
    """
    coefs: list[tuple[int, float, float]] = []
    if sharpness != 0.0:
        phi = 0.0 if sharpness > 0 else np.pi
        coefs.append((2, 0.3 * abs(sharpness), phi))
        coefs.append((4, 0.1 * abs(sharpness), phi))
    if asymmetry != 0.0:
        phi = np.pi / 2 if asymmetry > 0 else -np.pi / 2
        coefs.append((3, 0.2 * abs(asymmetry), phi))
        coefs.append((5, 0.05 * abs(asymmetry), phi))
    return coefs


# ── main synthesis function ────────────────────────────────────────────────


def synth_oscillator(
    pop: OscillatorPopulation,
    n_samples: int,
    sfreq: float,
    seed: int,
) -> OscillatorOutput:
    """Synthesise one oscillator population.

    carrier.std() == pop.amplitude (µV).
    bandwidth == 0 → pure sinusoid; bandwidth > 0 → AM band-limited noise.
    """
    internal_seeds: dict[str, int] = {}

    # 1. frequency trajectory
    if pop.paf_drift.sigma_hz == 0.0:
        f_t = np.full(n_samples, pop.center_frequency)
    else:
        paf_seed = derive(seed, "paf_drift")
        paf_rng = np.random.default_rng(paf_seed)
        f_t = _ou_frequency_trajectory(
            center_hz=pop.center_frequency,
            sigma_hz=pop.paf_drift.sigma_hz,
            tau_seconds=pop.paf_drift.tau_seconds,
            n_samples=n_samples,
            sfreq=sfreq,
            rng=paf_rng,
        )
        internal_seeds["paf_drift"] = paf_seed

    # 2. instantaneous phase
    phase_t = 2.0 * np.pi * np.cumsum(f_t) / sfreq

    # 3. carrier — pure sinusoid or band-limited noise
    if pop.bandwidth == 0.0:
        # sqrt(2)*cos gives std ≈ 1 before amplitude scaling
        env: float | np.ndarray = 1.0
        carrier = np.sqrt(2.0) * np.cos(phase_t)
    else:
        # Lowpass-filter noise then modulate by cos(phase_t).
        # Two seconds of throwaway samples absorbs filtfilt's edge transient.
        n_pad = int(2.0 * sfreq)
        rng = np.random.default_rng(seed)
        noise = rng.standard_normal(n_samples + n_pad)

        nyq = sfreq / 2.0
        cutoff = max(min((pop.bandwidth / 2.0) / nyq, 1.0 - 1e-4), 1e-4)
        b, a = sp_signal.butter(4, cutoff, btype="low")
        env = sp_signal.filtfilt(b, a, noise)[n_pad:]
        carrier = env * np.cos(phase_t)

    # 4. harmonic injection for non-sinusoidal waveform shapes
    if (
        pop.waveform_shape.peak_trough_sharpness != 0.0
        or pop.waveform_shape.rise_decay_asymmetry != 0.0
    ):
        for h, amp, phi in _harmonic_coefficients(
            pop.waveform_shape.peak_trough_sharpness,
            pop.waveform_shape.rise_decay_asymmetry,
        ):
            carrier = carrier + amp * env * np.cos(h * phase_t + phi)

    # 5. burst gating
    if pop.burst.mode == "bursty":
        burst_seed = derive(seed, "burst")
        burst_rng = np.random.default_rng(burst_seed)
        gate = burst_envelope(
            pop.burst,
            pop.center_frequency,
            n_samples,
            sfreq,
            burst_rng,
        )
        carrier = carrier * gate
        internal_seeds["burst"] = burst_seed

    # 6. amplitude scaling to absolute µV (std == pop.amplitude)
    std = carrier.std()
    if std > 0.0:
        carrier = carrier * (pop.amplitude / std)

    # 7. sharp-edge artifacts, injected after amplitude scaling
    if pop.artifact.rate_hz > 0.0:
        artifact_seed = derive(seed, "artifact")
        artifact_rng = np.random.default_rng(artifact_seed)
        artifact_amp = pop.artifact.amplitude_mult * carrier.std()
        onsets = schedule_class_events(
            pop.artifact.rate_hz,
            0.0,
            n_samples / sfreq,
            artifact_rng,
        )
        for onset_time in onsets:
            onset_sample = int(onset_time * sfreq)
            sign = int(artifact_rng.choice(np.array([-1, 1])))
            end = min(onset_sample + pop.artifact.width_samples, n_samples)
            carrier[onset_sample:end] += sign * artifact_amp
        internal_seeds["artifact"] = artifact_seed

    # 8. wrap phase to [-π, π]
    wrapped_phase = np.angle(np.exp(1j * phase_t))

    return OscillatorOutput(
        carrier=carrier.astype(np.float64),
        phase=wrapped_phase,
        internal_seeds=internal_seeds,
    )
