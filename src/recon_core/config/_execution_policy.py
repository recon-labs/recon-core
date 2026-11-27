"""Private execution-policy scope resolution, independent of connection payloads."""

from collections.abc import Callable, Mapping
from typing import Final

from recon_core.config._local_resource_policy import (
    _InvalidResourcePolicyError,
    _LocalResourceLayer,
    _LocalResourcePolicy,
    _mapping,
    _merge_local_resource_layers,
    _parse_duckdb_resource_layer,
)

# Private initial registry. External adapter schema registration is gated by M11-M12.
_POLICY_PARSERS: Final[Mapping[str, Callable[[object], _LocalResourceLayer]]] = {
    "duckdb": _parse_duckdb_resource_layer,
}


def _adapter_defaults(value: object) -> dict[str, _LocalResourceLayer]:
    adapters = _mapping(value, allowed=frozenset(_POLICY_PARSERS), location="execution.adapters")
    result: dict[str, _LocalResourceLayer] = {}
    for adapter_type, settings in adapters.items():
        layer = _POLICY_PARSERS[adapter_type](settings)
        if layer.authored_fields:
            result[adapter_type] = layer
    return result


def _parse_project_execution(value: object) -> dict[str, _LocalResourceLayer]:
    root = _mapping(value, allowed=frozenset({"adapters"}), location="execution")
    return _adapter_defaults(root.get("adapters", {}))


def _resolve_target_execution(
    value: object,
    *,
    project_defaults: Mapping[str, _LocalResourceLayer],
    declared_connections: Mapping[object, object],
    referenced_types: Mapping[str, str],
) -> dict[str, _LocalResourcePolicy]:
    root = _mapping(value, allowed=frozenset({"adapters", "connections"}), location="execution")
    target_defaults = _adapter_defaults(root.get("adapters", {}))
    allowed_names = frozenset(name for name in declared_connections if isinstance(name, str))
    overrides = _mapping(
        root.get("connections", {}), allowed=allowed_names, location="execution.connections"
    )
    result: dict[str, _LocalResourcePolicy] = {}
    for name, adapter_type in referenced_types.items():
        parser = _POLICY_PARSERS.get(adapter_type)
        if parser is None:
            if name in overrides:
                raise _InvalidResourcePolicyError(
                    "Operational policy is not supported for the referenced adapter."
                )
            continue
        connection_layer = parser(overrides[name]) if name in overrides else _LocalResourceLayer()
        result[name] = _merge_local_resource_layers(
            project_defaults.get(adapter_type, _LocalResourceLayer()),
            target_defaults.get(adapter_type, _LocalResourceLayer()),
            connection_layer,
        )
    return result

