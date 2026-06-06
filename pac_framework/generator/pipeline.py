"""Topological coupling orchestration."""
from __future__ import annotations

from collections import deque

import numpy as np

from pac_framework.generator.couplings import apply_phase_to_amplitude
from pac_framework.generator.oscillator import OscillatorOutput


def apply_couplings(
    outputs: dict[str, OscillatorOutput],
    couplings: list,
    chi_trajectories: dict[str, np.ndarray] | None = None,
) -> dict[str, np.ndarray]:
    """Return population ID → final carrier with PAC applied.

    PPC couplings contribute to topological ordering but are not synthesised.
    Raises ValueError for unknown IDs; RuntimeError for graph cycles (should
    be impossible if SignalConfig validation ran).
    """
    pop_ids = list(outputs.keys())

    for c in couplings:
        if c.driver not in outputs:
            raise ValueError(
                f"Coupling driver {c.driver!r} not found in outputs. "
                f"Available IDs: {list(outputs.keys())}"
            )
        if c.target not in outputs:
            raise ValueError(
                f"Coupling target {c.target!r} not found in outputs. "
                f"Available IDs: {list(outputs.keys())}"
            )

    # Build directed graph over all coupling kinds for topological sort.
    # Deduplicate edges so duplicate couplings don't distort in-degrees.
    in_degree: dict[str, int] = {pid: 0 for pid in pop_ids}
    adj: dict[str, list[str]] = {pid: [] for pid in pop_ids}
    seen_edges: set[tuple[str, str]] = set()
    for c in couplings:
        edge = (c.driver, c.target)
        if edge not in seen_edges:
            seen_edges.add(edge)
            adj[c.driver].append(c.target)
            in_degree[c.target] += 1

    # Kahn's algorithm: process nodes in pop_ids order for determinism
    queue: deque[str] = deque(pid for pid in pop_ids if in_degree[pid] == 0)
    topo_order: list[str] = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for nb in adj[node]:
            in_degree[nb] -= 1
            if in_degree[nb] == 0:
                queue.append(nb)

    if len(topo_order) != len(pop_ids):
        raise RuntimeError(
            "Coupling graph cycle detected at synthesis time — this should have "
            "been caught by SignalConfig validation."
        )

    carriers: dict[str, np.ndarray] = {
        pid: outputs[pid].carrier.copy() for pid in pop_ids
    }

    pac_by_target: dict[str, list] = {}
    for c in couplings:
        if c.kind == "phase_to_amplitude":
            pac_by_target.setdefault(c.target, []).append(c)

    trajectories = chi_trajectories or {}
    for pid in topo_order:
        for c in pac_by_target.get(pid, []):
            key = f"{c.driver}__to__{c.target}"
            chi = trajectories.get(key, c.chi)
            carriers[pid] = apply_phase_to_amplitude(
                carriers[pid],
                outputs[c.driver].phase,
                chi,
                c.phi_0,
                c.kappa,
            )

    return carriers
