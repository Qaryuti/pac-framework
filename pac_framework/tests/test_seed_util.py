"""Tests for pac_framework.core.seed_util.derive()."""
from __future__ import annotations

from pac_framework.core.seed_util import derive


def test_deterministic():
    assert derive(42, "a") == derive(42, "a")


def test_different_labels_differ():
    assert derive(42, "a") != derive(42, "b")


def test_different_seeds_differ():
    assert derive(42, "a") != derive(0, "a")


def test_label_ordering_matters():
    assert derive(42, "a", "b") != derive(42, "b", "a")


def test_joint_label_distinct_from_concatenated():
    # derive(seed, "a", "b") must differ from derive(seed, "ab")
    # because the NUL separator prevents "a"+"b" == "ab".
    assert derive(42, "a", "b") != derive(42, "ab")


def test_returns_int():
    assert isinstance(derive(42, "x"), int)


def test_multi_label_chain_deterministic():
    v1 = derive(derive(42, "subject", "test"), "session", 0)
    v2 = derive(derive(42, "subject", "test"), "session", 0)
    assert v1 == v2


def test_int_and_str_labels():
    # derive converts labels with str(), so integer 0 and string "0" hash
    # identically — that is the documented contract. Different ints differ.
    assert derive(42, 0) == derive(42, "0")   # str(0) == "0" by design
    assert derive(42, 1) != derive(42, 2)


def test_regression_known_values():
    """Hard-coded regression: if these values change, the seed hierarchy is broken."""
    assert derive(42, "a") == 13427196264944713351
    assert derive(42, "subject", "test") == 1284903911007720643
    assert derive(0, "a") == 15270482384145340437
