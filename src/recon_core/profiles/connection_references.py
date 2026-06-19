"""Connection-name references used by profile-aware workflows."""

from collections.abc import Iterable
from typing import Protocol


class ConnectionEndpointReference(Protocol):
    """Endpoint shape needed to derive referenced profile connections."""

    @property
    def connection(self) -> str:
        """Connection name referenced by the endpoint."""


class ContractConnectionReference(Protocol):
    """Contract shape needed to derive referenced profile connections."""

    @property
    def source(self) -> ConnectionEndpointReference:
        """Source endpoint reference."""

    @property
    def target(self) -> ConnectionEndpointReference:
        """Target endpoint reference."""


def connection_names_from_contracts(
    contracts: Iterable[ContractConnectionReference],
) -> tuple[str, ...]:
    """Return sorted unique connection names referenced by contracts."""
    names: set[str] = set()
    for contract in contracts:
        names.add(contract.source.connection)
        names.add(contract.target.connection)
    return tuple(sorted(names))


def referenced_connection_names(
    contracts: Iterable[ContractConnectionReference],
) -> tuple[str, ...]:
    """Return connection names referenced by selected authored contracts."""
    return connection_names_from_contracts(contracts)


def referenced_connection_names_from_compiled_contracts(
    contracts: Iterable[ContractConnectionReference],
) -> tuple[str, ...]:
    """Return connection names referenced by loaded compiled contracts."""
    return connection_names_from_contracts(contracts)
