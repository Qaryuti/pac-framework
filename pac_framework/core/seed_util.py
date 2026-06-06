from __future__ import annotations

import hashlib


def derive(parent_seed: int, *labels: int | str) -> int:
    """Derive a deterministic child seed using BLAKE2b over parent + labels.

    Each label is coerced to ``str`` before hashing, so an integer label and
    a string label with the same string representation produce the same child
    seed::

        derive(seed, 0) == derive(seed, "0")  # both hash "0"

    Callers that need distinct seeds for int and str labels must encode the
    distinction themselves (e.g. use ``("int", 0)`` vs ``("str", "0")``).
    """
    h = hashlib.blake2b(digest_size=8)
    h.update(str(parent_seed).encode())
    for label in labels:
        h.update(b"\x00")
        h.update(str(label).encode())
    return int.from_bytes(h.digest(), "little")
