"""Authored equivalence contract parsing."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser.files import ResourceFile
from recon_core.parser.models import SourceLocation

INVALID_CONTRACT = "RC_PARSE_INVALID_CONTRACT"
MISSING_REQUIRED_FIELD = "RC_PARSE_MISSING_REQUIRED_FIELD"
UNKNOWN_FIELD = "RC_PARSE_UNKNOWN_FIELD"
INVALID_ENDPOINT = "RC_PARSE_INVALID_ENDPOINT"

_MULTI_CONTRACT_KEYS = frozenset({"version", "contracts"})
_REQUIRED_CONTRACT_FIELDS = ("version", "name", "source", "target", "checks")
_ALLOWED_CONTRACT_FIELDS = frozenset(
    {
        "version",
        "name",
        "description",
        "source",
        "target",
        "grain",
        "columns",
        "metrics",
        "checks",
        "sampling",
        "tolerance_policy",
        "nulls",
        "schema",
        "cdc",
        "evidence",
        "owners",
        "tags",
    }
)


class AuthoredEndpointDict(TypedDict):
    connection: str
    relation: str | None
    query: str | None


class AuthoredContractSummaryDict(TypedDict):
    name: str
    version: int
    path: str
    tags: list[str]
    source: AuthoredEndpointDict
    target: AuthoredEndpointDict


@dataclass(frozen=True, slots=True)
class AuthoredEndpoint:
    """Authored source or target endpoint."""

    connection: str
    relation: str | None = None
    query: str | None = None

    def to_dict(self) -> AuthoredEndpointDict:
        return {
            "connection": self.connection,
            "relation": self.relation,
            "query": self.query,
        }


@dataclass(frozen=True, slots=True)
class AuthoredContract:
    """Structurally parsed authored equivalence contract."""

    name: str
    version: int
    source: AuthoredEndpoint
    target: AuthoredEndpoint
    source_location: SourceLocation
    checks: object
    description: str | None = None
    grain: dict[str, object] | None = None
    columns: dict[str, object] | None = None
    metrics: tuple[dict[str, object], ...] = ()
    sampling: dict[str, object] | None = None
    tolerance_policy: str | None = None
    nulls: dict[str, object] | None = None
    schema: dict[str, object] | None = None
    cdc: dict[str, object] | None = None
    evidence: dict[str, object] | None = None
    owners: dict[str, str] | None = None
    tags: tuple[str, ...] = ()

    def to_summary_dict(self) -> AuthoredContractSummaryDict:
        return {
            "name": self.name,
            "version": self.version,
            "path": self.source_location.path,
            "tags": list(self.tags),
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ContractParseResult:
    """Result for parsing authored contracts from one resource file."""

    contracts: tuple[AuthoredContract, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.diagnostics


def parse_contract_resource(resource_file: ResourceFile, data: object) -> ContractParseResult:
    """Parse one contract resource file into authored contracts."""
    diagnostics: list[Diagnostic] = []
    source_location = SourceLocation(path=resource_file.relative_path)

    if not isinstance(data, Mapping):
        return ContractParseResult(
            diagnostics=(
                _diagnostic(
                    resource_file,
                    INVALID_CONTRACT,
                    "Contract resource file must contain a top-level mapping.",
                ),
            )
        )

    raw_mapping = _string_key_mapping(data, resource_file, diagnostics)
    if raw_mapping is None:
        return ContractParseResult(diagnostics=tuple(diagnostics))

    contracts: tuple[AuthoredContract, ...]
    if "contracts" in raw_mapping:
        contracts = _parse_multi_contract_file(
            raw_mapping, source_location, resource_file, diagnostics
        )
    else:
        contract = _parse_contract_mapping(raw_mapping, source_location, resource_file, diagnostics)
        contracts = (contract,) if contract is not None else ()

    if diagnostics:
        return ContractParseResult(diagnostics=tuple(diagnostics))

    return ContractParseResult(contracts=contracts)


def _parse_multi_contract_file(
    raw_mapping: dict[str, object],
    source_location: SourceLocation,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> tuple[AuthoredContract, ...]:
    mixed_fields = sorted(set(raw_mapping) - _MULTI_CONTRACT_KEYS)
    if mixed_fields:
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                (
                    "Contract resource file cannot mix `contracts` with single-contract "
                    f"fields: {', '.join(mixed_fields)}"
                ),
            )
        )
        return ()

    version = _required_version(raw_mapping, resource_file, diagnostics)
    contracts_value = raw_mapping.get("contracts")
    if not isinstance(contracts_value, list | tuple):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                "Multi-contract field `contracts` must be a list of mappings.",
            )
        )
        return ()

    contracts: list[AuthoredContract] = []
    for index, raw_contract in enumerate(contracts_value):
        if not isinstance(raw_contract, Mapping):
            diagnostics.append(
                _diagnostic(
                    resource_file,
                    INVALID_CONTRACT,
                    f"Contract entry at index {index} must be a mapping.",
                )
            )
            continue

        contract_mapping = _string_key_mapping(raw_contract, resource_file, diagnostics)
        if contract_mapping is None:
            continue
        contract_mapping = dict(contract_mapping)
        contract_mapping.setdefault("version", version)

        contract = _parse_contract_mapping(
            contract_mapping, source_location, resource_file, diagnostics
        )
        if contract is not None:
            contracts.append(contract)

    return tuple(contracts)


def _parse_contract_mapping(
    raw_contract: dict[str, object],
    source_location: SourceLocation,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> AuthoredContract | None:
    start_diagnostic_count = len(diagnostics)
    _validate_unknown_fields(raw_contract, resource_file, diagnostics)
    _validate_required_fields(raw_contract, resource_file, diagnostics)

    version = _required_version(raw_contract, resource_file, diagnostics)
    name = _required_string(raw_contract, "name", resource_file, diagnostics)
    description = _optional_string(raw_contract, "description", resource_file, diagnostics)
    source = _required_endpoint(raw_contract, "source", resource_file, diagnostics)
    target = _required_endpoint(raw_contract, "target", resource_file, diagnostics)
    checks = _checks(raw_contract, resource_file, diagnostics)

    grain = _optional_object(raw_contract, "grain", resource_file, diagnostics)
    columns = _optional_object(raw_contract, "columns", resource_file, diagnostics)
    metrics = _optional_object_list(raw_contract, "metrics", resource_file, diagnostics)
    sampling = _optional_object(raw_contract, "sampling", resource_file, diagnostics)
    tolerance_policy = _optional_string(
        raw_contract, "tolerance_policy", resource_file, diagnostics
    )
    nulls = _optional_object(raw_contract, "nulls", resource_file, diagnostics)
    schema = _optional_object(raw_contract, "schema", resource_file, diagnostics)
    cdc = _optional_object(raw_contract, "cdc", resource_file, diagnostics)
    evidence = _optional_object(raw_contract, "evidence", resource_file, diagnostics)
    owners = _optional_string_object(raw_contract, "owners", resource_file, diagnostics)
    tags = _optional_string_list(raw_contract, "tags", resource_file, diagnostics)

    if len(diagnostics) > start_diagnostic_count:
        return None

    assert source is not None
    assert target is not None
    assert checks is not None
    assert name is not None
    assert version is not None

    return AuthoredContract(
        name=name,
        version=version,
        source=source,
        target=target,
        source_location=source_location,
        checks=checks,
        description=description,
        grain=grain,
        columns=columns,
        metrics=metrics,
        sampling=sampling,
        tolerance_policy=tolerance_policy,
        nulls=nulls,
        schema=schema,
        cdc=cdc,
        evidence=evidence,
        owners=owners,
        tags=tags,
    )


def _string_key_mapping(
    raw_mapping: Mapping[object, object],
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> dict[str, object] | None:
    mapping: dict[str, object] = {}
    for key, value in raw_mapping.items():
        if not isinstance(key, str):
            diagnostics.append(
                _diagnostic(
                    resource_file,
                    INVALID_CONTRACT,
                    "Contract mappings must use string keys.",
                )
            )
            return None
        mapping[key] = value
    return mapping


def _validate_unknown_fields(
    raw_contract: dict[str, object],
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> None:
    for field_name in sorted(set(raw_contract) - _ALLOWED_CONTRACT_FIELDS):
        diagnostics.append(
            _diagnostic(
                resource_file,
                UNKNOWN_FIELD,
                f"Unknown contract field: {field_name}",
                hint="Remove the field or use a documented contract field.",
            )
        )


def _validate_required_fields(
    raw_contract: dict[str, object],
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> None:
    for field_name in _REQUIRED_CONTRACT_FIELDS:
        if field_name in raw_contract:
            continue
        diagnostics.append(
            _diagnostic(
                resource_file,
                MISSING_REQUIRED_FIELD,
                f"Missing required contract field: {field_name}",
                hint=f"Add `{field_name}: <value>` to the contract.",
            )
        )


def _required_version(
    raw_contract: dict[str, object],
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> int | None:
    value = raw_contract.get("version")
    if value is None:
        return None
    if type(value) is not int:
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                "Contract field `version` must be an integer.",
                hint="Use `version: 1`.",
            )
        )
        return None
    return value


def _required_string(
    raw_contract: dict[str, object],
    field_name: str,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> str | None:
    value = raw_contract.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or value == "":
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                f"Contract field `{field_name}` must be a non-empty string.",
            )
        )
        return None
    return value


def _optional_string(
    raw_contract: dict[str, object],
    field_name: str,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> str | None:
    if field_name not in raw_contract or raw_contract[field_name] is None:
        return None
    return _required_string(raw_contract, field_name, resource_file, diagnostics)


def _required_endpoint(
    raw_contract: dict[str, object],
    field_name: str,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> AuthoredEndpoint | None:
    value = raw_contract.get(field_name)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_ENDPOINT,
                f"Endpoint `{field_name}` must be a mapping.",
            )
        )
        return None

    endpoint_mapping = _string_key_mapping(value, resource_file, diagnostics)
    if endpoint_mapping is None:
        return None

    endpoint_diagnostics_start = len(diagnostics)
    connection = endpoint_mapping.get("connection")
    if not isinstance(connection, str) or connection == "":
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_ENDPOINT,
                f"Endpoint `{field_name}` requires a non-empty `connection`.",
            )
        )

    relation = endpoint_mapping.get("relation")
    query = endpoint_mapping.get("query")
    relation_text: str | None = relation if isinstance(relation, str) and relation != "" else None
    query_text: str | None = query if isinstance(query, str) and query != "" else None
    if (relation_text is not None) == (query_text is not None):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_ENDPOINT,
                f"Endpoint `{field_name}` must define exactly one of `relation` or `query`.",
            )
        )

    if len(diagnostics) > endpoint_diagnostics_start:
        return None

    assert isinstance(connection, str)
    return AuthoredEndpoint(
        connection=connection,
        relation=relation_text,
        query=query_text,
    )


def _checks(
    raw_contract: dict[str, object],
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> object | None:
    value = raw_contract.get("checks")
    if value is None:
        return None
    if not isinstance(value, Mapping | list | tuple):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                "Contract field `checks` must be a mapping or list.",
            )
        )
        return None
    if isinstance(value, Mapping):
        return dict(value)
    return tuple(value)


def _optional_object(
    raw_contract: dict[str, object],
    field_name: str,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> dict[str, object] | None:
    if field_name not in raw_contract or raw_contract[field_name] is None:
        return None
    value = raw_contract[field_name]
    if not isinstance(value, Mapping):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                f"Contract field `{field_name}` must be a mapping.",
            )
        )
        return None
    mapping = _string_key_mapping(value, resource_file, diagnostics)
    return dict(mapping) if mapping is not None else None


def _optional_object_list(
    raw_contract: dict[str, object],
    field_name: str,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> tuple[dict[str, object], ...]:
    if field_name not in raw_contract or raw_contract[field_name] is None:
        return ()
    value = raw_contract[field_name]
    if not isinstance(value, Sequence) or isinstance(value, str):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                f"Contract field `{field_name}` must be a list of mappings.",
            )
        )
        return ()

    parsed_values: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, Mapping):
            diagnostics.append(
                _diagnostic(
                    resource_file,
                    INVALID_CONTRACT,
                    f"Contract field `{field_name}` must contain only mappings.",
                )
            )
            return ()
        mapping = _string_key_mapping(item, resource_file, diagnostics)
        if mapping is None:
            return ()
        parsed_values.append(dict(mapping))
    return tuple(parsed_values)


def _optional_string_object(
    raw_contract: dict[str, object],
    field_name: str,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> dict[str, str] | None:
    if field_name not in raw_contract or raw_contract[field_name] is None:
        return None
    value = raw_contract[field_name]
    if not isinstance(value, Mapping):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                f"Contract field `{field_name}` must be a mapping of strings.",
            )
        )
        return None

    parsed: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            diagnostics.append(
                _diagnostic(
                    resource_file,
                    INVALID_CONTRACT,
                    f"Contract field `{field_name}` must be a mapping of strings.",
                )
            )
            return None
        parsed[key] = item
    return parsed


def _optional_string_list(
    raw_contract: dict[str, object],
    field_name: str,
    resource_file: ResourceFile,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    if field_name not in raw_contract or raw_contract[field_name] is None:
        return ()
    value = raw_contract[field_name]
    if not isinstance(value, Sequence) or isinstance(value, str):
        diagnostics.append(
            _diagnostic(
                resource_file,
                INVALID_CONTRACT,
                f"Contract field `{field_name}` must be a list of strings.",
            )
        )
        return ()

    tags: list[str] = []
    for item in value:
        if not isinstance(item, str) or item == "":
            diagnostics.append(
                _diagnostic(
                    resource_file,
                    INVALID_CONTRACT,
                    f"Contract field `{field_name}` must contain only non-empty strings.",
                )
            )
            return ()
        tags.append(item)
    return tuple(tags)


def _diagnostic(
    resource_file: ResourceFile,
    code: str,
    message: str,
    *,
    hint: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="contract",
        path=resource_file.relative_path,
        hint=hint,
    )
