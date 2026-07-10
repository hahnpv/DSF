"""
Unit tests for dsf.utils.validate_config (load-time strict validation).

Structural errors always fire; registry-driven checks fire only for block types
the ModelRegistry knows (Mass/Tank/RocketProp/Vehicle). Unknown attribute names
are warnings (the registry is an MVP and may lag the C++ models); enum and
numeric-type violations are errors.
"""
import os
import pytest

from dsf.utils.validate_config import (
    validate_dsf, enforce_config, ConfigValidationError,
)
from dsf.gui.core.model_registry import ModelRegistry

REG = ModelRegistry()


def _cfg(blocks=None, connections=None, metadata=None):
    return {
        "blocks": blocks or [],
        "connections": connections or [],
        "metadata": metadata or {"dt": 0.1, "tmax": 10.0},
    }


def test_valid_minimal():
    cfg = _cfg(blocks=[{"id": "m1", "type": "Mass", "parameters": {"mass": 5.0}}])
    errs, warns = validate_dsf(cfg, REG)
    assert errs == []


@pytest.mark.parametrize("meta,frag", [
    ({"dt": 0.0, "tmax": 10.0}, "dt"),
    ({"dt": -1, "tmax": 10.0}, "dt"),
    ({"tmax": 10.0}, "dt"),                 # missing dt
    ({"dt": 0.1, "tmax": 0}, "tmax"),
    ({"dt": 0.1}, "tmax"),                  # missing tmax
])
def test_bad_timing(meta, frag):
    errs, _ = validate_dsf(_cfg(metadata=meta), REG)
    assert any(frag in e for e in errs), errs


def test_duplicate_ids():
    errs, _ = validate_dsf(_cfg(blocks=[
        {"id": "x", "type": "Mass"}, {"id": "x", "type": "Mass"}]), REG)
    assert any("duplicate" in e for e in errs)


def test_dangling_connection():
    errs, _ = validate_dsf(_cfg(
        blocks=[{"id": "a", "type": "Mass"}],
        connections=[{"from_block": "a", "to_block": "ghost"}]), REG)
    assert any("ghost" in e for e in errs)


def test_dangling_parent():
    errs, _ = validate_dsf(_cfg(
        blocks=[{"id": "a", "type": "Mass", "parent_id": "nope"}]), REG)
    assert any("nope" in e for e in errs)


def test_unknown_attribute_is_warning():
    errs, warns = validate_dsf(_cfg(
        blocks=[{"id": "m", "type": "Mass", "parameters": {"masss": 5.0}}]), REG)
    assert errs == []
    assert any("masss" in w for w in warns)


def test_enum_violation_is_error():
    errs, _ = validate_dsf(_cfg(
        blocks=[{"id": "t", "type": "Tank", "parameters": {"geometry": "banana"}}]), REG)
    assert any("geometry" in e for e in errs)


def test_non_numeric_is_error():
    errs, _ = validate_dsf(_cfg(
        blocks=[{"id": "m", "type": "Mass", "parameters": {"mass": "heavy"}}]), REG)
    assert any("mass" in e and "numeric" in e for e in errs)


def test_unknown_type_skips_registry_checks():
    # A class the registry doesn't know (e.g. a C++-only model) must not be
    # flagged for unknown attributes.
    errs, warns = validate_dsf(_cfg(
        blocks=[{"id": "s", "type": "SomeCppModel", "parameters": {"whatever": 1}}]), REG)
    assert errs == [] and warns == []


def test_enforce_raises_by_default():
    with pytest.raises(ConfigValidationError):
        enforce_config(_cfg(metadata={"dt": 0.0, "tmax": 10.0}))


def test_enforce_warn_mode_downgrades(monkeypatch):
    monkeypatch.setenv("DSF_VALIDATE", "warn")
    # Should NOT raise even with an error present.
    enforce_config(_cfg(metadata={"dt": 0.0, "tmax": 10.0}))
