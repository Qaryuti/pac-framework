"""Von Mises PAC kernel and Tukey event-modulation envelope."""
from __future__ import annotations

import numpy as np


def build_window_envelope(
    onset_samples: np.ndarray,
    window_sec: float,
    latency_sec: float,
    edge_fraction: float,
    n_samples: int,
    sfreq: float,
) -> np.ndarray:
    """Build a [0, 1] modulation envelope from a set of event onsets.

    For each onset a Tukey (flat-topped raised-cosine) window of width
    *window_sec* is stamped into the output starting *latency_sec* after
    the event sample.  Contributions from overlapping events are combined
    by elementwise max.

    Parameters
    ----------
    onset_samples : 1-D int array  Sample indices of event onsets.
    window_sec    : float          Total window duration in seconds (> 0).
    latency_sec   : float          Delay from event onset to window start (>= 0).
    edge_fraction : float          Fraction of window spent on each cosine ramp
                                   (in [0, 0.5]).  0 → rectangular, 0.5 → Hann.
    n_samples     : int            Output length in samples.
    sfreq         : float          Sampling frequency in Hz.

    Returns
    -------
    env : float64 ndarray, shape (n_samples,), values in [0, 1].
    """
    window_samp = max(1, round(window_sec * sfreq))
    latency_samp = round(latency_sec * sfreq)
    edge_samp = min(window_samp // 2, round(edge_fraction * window_samp))

    template = np.ones(window_samp, dtype=np.float64)
    if edge_samp > 0:
        ramp = 0.5 * (1.0 - np.cos(np.pi * np.arange(edge_samp) / edge_samp))
        template[:edge_samp] = ramp
        template[window_samp - edge_samp:] = ramp[::-1]

    env = np.zeros(n_samples, dtype=np.float64)
    for onset in onset_samples:
        start = int(onset) + latency_samp
        end = start + window_samp
        # Clip to signal bounds
        src_start = max(0, -start)
        dst_start = max(0, start)
        src_end = src_start + (min(end, n_samples) - dst_start)
        if src_end <= src_start:
            continue
        np.maximum(
            env[dst_start: dst_start + (src_end - src_start)],
            template[src_start:src_end],
            out=env[dst_start: dst_start + (src_end - src_start)],
        )

    return env


def apply_phase_to_amplitude(
    target_carrier: np.ndarray,
    driver_phase: np.ndarray,
    chi: float | np.ndarray,
    phi_0: float,
    kappa: float,
) -> np.ndarray:
    """Apply the von Mises envelope to *target_carrier*.

    E(φ; χ, φ₀, κ) = (1 - χ) + χ · exp(κ · cos(φ - φ₀) - κ)

    Subtracting κ in the exponent keeps the envelope in [0, 1] without
    exp(κ) overflow.  χ=0 or κ=0 both leave the carrier unchanged.
    *chi* may be a scalar or a 1-D ndarray of length n_samples.
    """
    if isinstance(chi, np.ndarray):
        if chi.shape != target_carrier.shape:
            raise ValueError(
                f"chi array length {chi.shape} does not match carrier "
                f"length {target_carrier.shape}."
            )
    envelope = (1.0 - chi) + chi * np.exp(kappa * np.cos(driver_phase - phi_0) - kappa)
    return (target_carrier * envelope).astype(np.float64)
