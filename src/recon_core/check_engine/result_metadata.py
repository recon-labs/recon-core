"""Neutral result metadata helpers for check-engine modules."""

from collections.abc import Mapping

from recon_core.artifacts import LoadedCompiledCheck


def identity_label(check: LoadedCompiledCheck) -> str | None:
    """Return the check identity kind for result display."""
    payload = check.payload
    if payload is None:
        return None
    identity = payload.get("identity")
    if not isinstance(identity, Mapping):
        return None
    kind = identity.get("kind")
    return kind if isinstance(kind, str) else None
