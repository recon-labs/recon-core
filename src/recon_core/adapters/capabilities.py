"""Adapter capability support states and validation."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

ADAPTER_CAPABILITY_UNSUPPORTED = "RC_ADAPTER_CAPABILITY_UNSUPPORTED"


class CapabilitySupport(StrEnum):
    """Adapter support state for one capability."""

    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    NOT_IMPLEMENTED = "not_implemented"
    VERSIONED = "versioned"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class AdapterCapabilities:
    """Declared adapter capabilities."""

    support: Mapping[str, CapabilitySupport]

    def support_for(self, capability: str) -> CapabilitySupport:
        """Return the declared support state for a capability."""
        return self.support.get(capability, CapabilitySupport.UNKNOWN)

    def satisfies(self, capability: str) -> bool:
        """Return whether this adapter currently satisfies a required capability."""
        return self.support_for(capability) is CapabilitySupport.FULL


def validate_required_capabilities(
    *,
    adapter_type: str,
    capabilities: AdapterCapabilities,
    required_capabilities: tuple[str, ...],
) -> tuple[Diagnostic, ...]:
    """Validate that an adapter satisfies required capabilities."""
    diagnostics: list[Diagnostic] = []

    for capability in required_capabilities:
        support = capabilities.support_for(capability)
        if support is CapabilitySupport.FULL:
            continue
        diagnostics.append(
            Diagnostic(
                code=ADAPTER_CAPABILITY_UNSUPPORTED,
                severity=DiagnosticSeverity.ERROR,
                message=(
                    f"Adapter `{adapter_type}` does not satisfy required capability "
                    f"`{capability}`; support state `{_support_state_label(support)}`."
                ),
                resource_type="adapter_capability",
                resource_name=capability,
                hint="Use an adapter that supports this capability or change the check scope.",
            )
        )

    return tuple(diagnostics)


def _support_state_label(support: object) -> str:
    if isinstance(support, CapabilitySupport):
        return support.value
    return "invalid support state"
