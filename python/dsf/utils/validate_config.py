"""
dsf.utils.validate_config
-------------------------
Load-time validation for a parsed ``.dsf`` project dict. Catches the class of
"the sim runs but is quietly wrong" errors that the C++ layer swallows via
silent zero-substitution (a typo'd attribute becomes 0.0, a dangling connection
resolves to nothing, dt=0 loops forever).

Two tiers (see the code-review decision):
  * Structural — always checked, zero false positives: dt/tmax present & > 0,
    unique non-empty block ids, connections/parent refs point at existing blocks.
  * Registry-driven — only for block types the GUI ModelRegistry knows about:
    unknown attribute names (typos), enum values outside the allowed set, and
    non-numeric values for numeric properties.

Enforcement is FAIL-BY-DEFAULT: `enforce_config` raises on any error. Set the
environment variable ``DSF_VALIDATE=warn`` (or ``lax``/``off``/``0``) to
downgrade errors to warnings for a deck that legitimately trips the checks.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Tuple

# Connection/pointer attributes that reference another block by id.
_POINTER_ATTRS = {"nav", "control", "guidance", "prop", "parent", "target"}


class ConfigValidationError(Exception):
    """Raised by enforce_config when validation fails in strict (default) mode."""


def _is_number(v: Any) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def validate_dsf(data: Dict[str, Any], registry=None) -> Tuple[List[str], List[str]]:
    """Validate a parsed .dsf project dict. Returns (errors, warnings)."""
    errors: List[str] = []
    warnings: List[str] = []

    blocks = data.get("blocks", []) or []
    connections = data.get("connections", []) or []
    metadata = data.get("metadata", {}) or {}

    # ── Structural: timing ────────────────────────────────────────────────
    for key in ("dt", "tmax"):
        val = metadata.get(key)
        if val is None:
            errors.append(f"metadata '{key}' is missing")
        elif not _is_number(val):
            errors.append(f"metadata '{key}'={val!r} is not a number")
        elif float(val) <= 0:
            errors.append(f"metadata '{key}' must be > 0 (got {val})")

    # ── Structural: block ids ─────────────────────────────────────────────
    id_set = set()
    for b in blocks:
        bid = b.get("id")
        if not bid:
            errors.append(f"a block of class '{b.get('type', '?')}' has no id")
            continue
        if bid in id_set:
            errors.append(f"duplicate block id '{bid}'")
        id_set.add(bid)
        if not b.get("type"):
            errors.append(f"block '{bid}' has no class/type")

    # ── Structural: references resolve ────────────────────────────────────
    for b in blocks:
        pid = b.get("parent_id")
        if pid and pid not in id_set:
            errors.append(f"block '{b.get('id')}': parent_id '{pid}' references an unknown block")
    for c in connections:
        for end in ("from_block", "to_block"):
            ref = c.get(end)
            if ref and ref not in id_set:
                errors.append(f"connection {end} '{ref}' references an unknown block")

    # ── Registry-driven: attribute names / enums / numeric types ──────────
    if registry is not None:
        for b in blocks:
            bdef = registry.get_block(b.get("type"))
            if bdef is None:
                continue   # type unknown to the registry (e.g. a C++-only model)
            props = {p.name: p for p in bdef.properties}
            for k, v in (b.get("parameters") or {}).items():
                pdef = props.get(k)
                if pdef is None:
                    warnings.append(
                        f"block '{b.get('id')}': attribute '{k}' is not defined for "
                        f"class '{b.get('type')}' (typo? the sim silently ignores it)")
                    continue
                if pdef.options and str(v) not in [str(o) for o in pdef.options]:
                    errors.append(
                        f"block '{b.get('id')}': {k}={v!r} is not one of {pdef.options}")
                if pdef.type in ("float", "double", "int") and not _is_number(v):
                    errors.append(
                        f"block '{b.get('id')}': {k}={v!r} is not numeric ({pdef.type})")

    return errors, warnings


def _strict_enabled() -> bool:
    return os.environ.get("DSF_VALIDATE", "strict").lower() not in (
        "warn", "lax", "off", "0", "false", "no")


def enforce_config(data: Dict[str, Any]) -> None:
    """Validate `data`; print warnings, and raise ConfigValidationError on any
    error unless DSF_VALIDATE downgrades to warn-only."""
    registry = None
    try:
        # model_registry is Qt-free, so this is safe in the headless run path.
        from dsf.gui.core.model_registry import ModelRegistry
        registry = ModelRegistry()
    except Exception:
        registry = None   # registry-driven checks simply skipped if unavailable

    errors, warnings = validate_dsf(data, registry)

    for w in warnings:
        print(f"[config warning] {w}", file=sys.stderr)

    if not errors:
        return

    if _strict_enabled():
        detail = "\n  - ".join(errors)
        raise ConfigValidationError(
            "Configuration validation failed:\n  - " + detail +
            "\n(set DSF_VALIDATE=warn to downgrade these to warnings)")
    else:
        for e in errors:
            print(f"[config error] {e}", file=sys.stderr)
