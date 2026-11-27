"""Connection profile models."""

from dataclasses import dataclass, field
from typing import Any

from recon_core.config._local_resource_policy import _LocalResourcePolicy
from recon_core.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Rendered connection config for one selected profile target."""

    name: str
    type: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SelectedProfile:
    """Selected profile target and referenced connection configs."""

    name: str
    target_name: str
    connections: dict[str, ConnectionConfig]
    _execution_policies: dict[str, _LocalResourcePolicy] = field(
        default_factory=dict, repr=False, compare=False, kw_only=True
    )


@dataclass(frozen=True, slots=True)
class ProfileLoadResult:
    """Result for loading a selected connection profile."""

    profile: SelectedProfile | None = None
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.profile is not None and not self.diagnostics
