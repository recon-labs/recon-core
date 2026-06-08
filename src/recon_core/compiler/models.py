"""Compiler models for typed check plans and public compiler catalog values."""

from dataclasses import dataclass
from enum import StrEnum
from typing import NotRequired, TypedDict

from recon_core.diagnostics import Diagnostic, DiagnosticDict

COMPILED_ARTIFACT_VERSION = 1


class CompiledArtifactType(StrEnum):
    """Compiled artifact type names."""

    COMPILED_CONTRACT = "compiled_contract"
    COMPILED_CHECKS = "compiled_checks"


class CheckOriginKind(StrEnum):
    """Reason a compiled check exists."""

    EXPLICIT_CHECK = "explicit_check"
    METRIC = "metric"
    CHECK_PACK = "check_pack"
    FRAMEWORK_REQUIRED_SAFETY_CHECK = "framework_required_safety_check"


class CompiledCheckType(StrEnum):
    """Compiled check type names."""

    ROW_COUNT_DIFF = "row_count_diff"
    SUM_DIFF = "sum_diff"
    GROUPED_AGGREGATE_DIFF = "grouped_aggregate_diff"
    MISSING_KEYS = "missing_keys"
    EXTRA_KEYS = "extra_keys"
    NULL_SOURCE_KEYS = "null_source_keys"
    NULL_TARGET_KEYS = "null_target_keys"
    DUPLICATE_SOURCE_KEYS = "duplicate_source_keys"
    DUPLICATE_TARGET_KEYS = "duplicate_target_keys"


class IdentityKind(StrEnum):
    """Identity role used by a check or operation."""

    NONE = "none"
    GRAIN = "grain"
    CDC = "cdc"


class RenderingStatus(StrEnum):
    """SQL rendering status for a compiled check."""

    NOT_RENDERED = "not_rendered"
    RENDERED = "rendered"
    BLOCKED = "blocked"
    FAILED = "failed"


class BlockingPolicyValue(StrEnum):
    """Runtime behavior when prerequisite checks fail."""

    SKIPPED = "skipped"


class OperationSide(StrEnum):
    """Source or target side for side-specific operations."""

    SOURCE = "source"
    TARGET = "target"


class KeyDiffDirection(StrEnum):
    """Direction for source-target key presence checks."""

    SOURCE_MINUS_TARGET = "source_minus_target"
    TARGET_MINUS_SOURCE = "target_minus_source"


class OperationType(StrEnum):
    """Core-owned typed operation names."""

    ROW_COUNT = "row_count"
    COMPARE_COUNTS = "compare_counts"
    KEY_DIFF = "key_diff"
    NULL_KEY = "null_key"
    DUPLICATE_KEY = "duplicate_key"
    AGGREGATE = "aggregate"
    GROUPED_AGGREGATE = "grouped_aggregate"
    COMPARE_AGGREGATES = "compare_aggregates"
    COMPARE_GROUPED_AGGREGATES = "compare_grouped_aggregates"
    NULL_SAFE_EQUAL = "null_safe_equal"
    CAST = "cast"
    LIMIT = "limit"
    HASH = "hash"
    TIMESTAMP_DIFF = "timestamp_diff"
    SCHEMA_METADATA = "schema_metadata"


class AdapterCapability(StrEnum):
    """Draft adapter capability names used by typed plans."""

    RELATIONS = "relations"
    QUERIES = "queries"
    METADATA_COLUMNS = "metadata_columns"
    METADATA_PRECISION_SCALE = "metadata_precision_scale"
    TEMP_TABLES = "temp_tables"
    CTE_SUPPORT = "cte_support"
    ROW_COUNT = "row_count"
    AGGREGATE = "aggregate"
    GROUPED_AGGREGATE = "grouped_aggregate"
    KEY_DIFF = "key_diff"
    NULL_KEY = "null_key"
    DUPLICATE_KEY = "duplicate_key"
    NULL_SAFE_EQUALITY = "null_safe_equality"
    NUMERIC_CAST = "numeric_cast"
    STRING_CAST = "string_cast"
    TIMESTAMP_DIFF = "timestamp_diff"
    SAFE_HASH_EXPRESSION = "safe_hash_expression"
    PORTABLE_HASH_COMPATIBLE = "portable_hash_compatible"
    JSON_PATH = "json_path"
    SEMI_STRUCTURED_PROJECTION = "semi_structured_projection"
    SCHEMA_METADATA = "schema_metadata"


_OPERATION_ALLOWED_FIELDS: dict[OperationType, frozenset[str]] = {
    OperationType.ROW_COUNT: frozenset({"side"}),
    OperationType.COMPARE_COUNTS: frozenset(),
    OperationType.KEY_DIFF: frozenset({"direction", "identity"}),
    OperationType.NULL_KEY: frozenset({"side", "identity"}),
    OperationType.DUPLICATE_KEY: frozenset({"side", "identity"}),
    OperationType.AGGREGATE: frozenset({"side", "aggregate", "column"}),
    OperationType.GROUPED_AGGREGATE: frozenset({"side", "aggregate", "column", "group_by"}),
    OperationType.COMPARE_AGGREGATES: frozenset(),
    OperationType.COMPARE_GROUPED_AGGREGATES: frozenset(),
}


class IdentityDict(TypedDict):
    kind: str
    keys: list[str]


class TypedOperationDict(TypedDict):
    type: str
    side: NotRequired[str]
    direction: NotRequired[str]
    identity: NotRequired[IdentityDict]
    aggregate: NotRequired[str]
    column: NotRequired[str]
    group_by: NotRequired[list[str]]


class CheckPlanDict(TypedDict):
    id: str
    operations: list[TypedOperationDict]
    required_capabilities: list[str]


class CheckOriginDict(TypedDict):
    kind: str
    name: NotRequired[str]
    required_by: NotRequired[list[str]]


class CheckRequirementsDict(TypedDict):
    requires_grain_keys: bool
    requires_non_null_grain: bool
    requires_unique_grain: bool
    requires_cdc_keys: bool
    required_columns: list[str]
    required_metrics: list[str]
    required_capabilities: list[str]


class BlockingPolicyDict(TypedDict):
    on_prerequisite_failure: str


class RenderingDict(TypedDict):
    status: str
    sql_paths: list[str]
    adapter_type: NotRequired[str]


class ResolvedSamplingDict(TypedDict, total=False):
    mode: str
    policy: str


class CompiledMetricDict(TypedDict):
    type: str
    column: str
    group_by: list[str]


class CompiledCheckDict(TypedDict):
    id: str
    name: str
    type: str
    origin: CheckOriginDict
    identity: IdentityDict
    requirements: CheckRequirementsDict
    sampling: ResolvedSamplingDict
    tolerance: object | None
    metric: NotRequired[CompiledMetricDict]
    prerequisites: list[str]
    blocking_policy: BlockingPolicyDict
    plan: CheckPlanDict
    rendering: RenderingDict
    diagnostics: list[DiagnosticDict]


class CompiledProjectDict(TypedDict):
    name: str
    version: str | None


class CompiledContractReferenceDict(TypedDict):
    id: str
    name: str
    source_file: str
    authored_version: NotRequired[int]


class CompiledEndpointDict(TypedDict):
    connection: str
    relation: str | None
    query: str | None


class CompiledGrainIdentityDict(TypedDict):
    keys: list[str]


class CompiledContractIdentityDict(TypedDict):
    grain: CompiledGrainIdentityDict
    cdc: object | None


class CompiledContractPoliciesDict(TypedDict):
    sampling: object | None
    tolerance_policy: object | None
    nulls: object | None
    schema: object | None
    cdc: object | None
    evidence: object | None


class CompiledContractArtifactDict(TypedDict):
    artifact_type: str
    artifact_version: int
    recon_version: str
    generated_at: str
    invocation_id: str
    project: CompiledProjectDict
    contract: CompiledContractReferenceDict
    source: CompiledEndpointDict
    target: CompiledEndpointDict
    identity: CompiledContractIdentityDict
    columns: object | None
    metrics: list[dict[str, object]]
    policies: CompiledContractPoliciesDict
    diagnostics: list[DiagnosticDict]


class CompiledChecksArtifactDict(TypedDict):
    artifact_type: str
    artifact_version: int
    recon_version: str
    generated_at: str
    invocation_id: str
    project: CompiledProjectDict
    contract: CompiledContractReferenceDict
    checks: list[CompiledCheckDict]
    diagnostics: list[DiagnosticDict]


@dataclass(frozen=True, slots=True)
class Identity:
    """Resolved identity used by a compiled check or typed operation."""

    kind: IdentityKind
    keys: tuple[str, ...] = ()

    def to_dict(self) -> IdentityDict:
        return {
            "kind": self.kind.value,
            "keys": list(self.keys),
        }


@dataclass(frozen=True, slots=True)
class ResolvedSampling:
    """Resolved sampling metadata preserved on compiled checks."""

    mode: str | None = "full"
    policy: str | None = None

    def to_dict(self) -> ResolvedSamplingDict:
        sampling: ResolvedSamplingDict = {}
        if self.mode is not None:
            sampling["mode"] = self.mode
        if self.policy is not None:
            sampling["policy"] = self.policy
        return sampling


@dataclass(frozen=True, slots=True)
class CompiledMetric:
    """Metric metadata preserved on a metric-generated compiled check."""

    metric_type: str
    column: str
    group_by: tuple[str, ...] = ()

    def to_dict(self) -> CompiledMetricDict:
        return {
            "type": self.metric_type,
            "column": self.column,
            "group_by": list(self.group_by),
        }


@dataclass(frozen=True, slots=True)
class CompiledProject:
    """Project metadata included in compiled artifacts."""

    name: str
    version: str | None = None

    def to_dict(self) -> CompiledProjectDict:
        return {
            "name": self.name,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class CompiledContractReference:
    """Contract metadata included in compiled artifacts."""

    id: str
    name: str
    source_file: str
    authored_version: int | None = None

    def to_dict(self) -> CompiledContractReferenceDict:
        contract: CompiledContractReferenceDict = {
            "id": self.id,
            "name": self.name,
            "source_file": self.source_file,
        }
        if self.authored_version is not None:
            contract["authored_version"] = self.authored_version
        return contract


@dataclass(frozen=True, slots=True)
class CompiledEndpoint:
    """Resolved endpoint metadata included in compiled artifacts."""

    connection: str
    relation: str | None = None
    query: str | None = None

    def to_dict(self) -> CompiledEndpointDict:
        return {
            "connection": self.connection,
            "relation": self.relation,
            "query": self.query,
        }


@dataclass(frozen=True, slots=True)
class CompiledContractPolicies:
    """Policy metadata included in compiled contract artifacts."""

    sampling: object | None = None
    tolerance_policy: object | None = None
    nulls: object | None = None
    schema: object | None = None
    cdc: object | None = None
    evidence: object | None = None

    def to_dict(self) -> CompiledContractPoliciesDict:
        return {
            "sampling": self.sampling,
            "tolerance_policy": self.tolerance_policy,
            "nulls": self.nulls,
            "schema": self.schema,
            "cdc": self.cdc,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class CheckOrigin:
    """Reason a compiled check was generated."""

    kind: CheckOriginKind
    name: str | None = None
    required_by: tuple[str, ...] = ()

    def to_dict(self) -> CheckOriginDict:
        origin: CheckOriginDict = {"kind": self.kind.value}
        if self.name is not None:
            origin["name"] = self.name
        if self.required_by:
            origin["required_by"] = list(self.required_by)
        return origin


@dataclass(frozen=True, slots=True)
class CheckRequirements:
    """Resolved requirements for a compiled check."""

    requires_grain_keys: bool = False
    requires_non_null_grain: bool = False
    requires_unique_grain: bool = False
    requires_cdc_keys: bool = False
    required_columns: tuple[str, ...] = ()
    required_metrics: tuple[str, ...] = ()
    required_capabilities: tuple[AdapterCapability, ...] = ()

    def to_dict(self) -> CheckRequirementsDict:
        return {
            "requires_grain_keys": self.requires_grain_keys,
            "requires_non_null_grain": self.requires_non_null_grain,
            "requires_unique_grain": self.requires_unique_grain,
            "requires_cdc_keys": self.requires_cdc_keys,
            "required_columns": list(self.required_columns),
            "required_metrics": list(self.required_metrics),
            "required_capabilities": [
                capability.value for capability in self.required_capabilities
            ],
        }


@dataclass(frozen=True, slots=True)
class BlockingPolicy:
    """Runtime behavior for checks blocked by prerequisite failures."""

    on_prerequisite_failure: BlockingPolicyValue = BlockingPolicyValue.SKIPPED

    def to_dict(self) -> BlockingPolicyDict:
        return {"on_prerequisite_failure": self.on_prerequisite_failure.value}


@dataclass(frozen=True, slots=True)
class Rendering:
    """SQL rendering metadata for a compiled check."""

    status: RenderingStatus = RenderingStatus.NOT_RENDERED
    sql_paths: tuple[str, ...] = ()
    adapter_type: str | None = None

    def to_dict(self) -> RenderingDict:
        rendering: RenderingDict = {
            "status": self.status.value,
            "sql_paths": list(self.sql_paths),
        }
        if self.adapter_type is not None:
            rendering["adapter_type"] = self.adapter_type
        return rendering


@dataclass(frozen=True, slots=True)
class TypedOperation:
    """One core-owned operation in a typed check plan."""

    type: OperationType
    side: OperationSide | None = None
    direction: KeyDiffDirection | None = None
    identity: Identity | None = None
    aggregate_function: str | None = None
    column: str | None = None
    group_by: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def row_count(cls, *, side: OperationSide) -> "TypedOperation":
        return cls(type=OperationType.ROW_COUNT, side=side)

    @classmethod
    def compare_counts(cls) -> "TypedOperation":
        return cls(type=OperationType.COMPARE_COUNTS)

    @classmethod
    def key_diff(cls, *, direction: KeyDiffDirection, identity: Identity) -> "TypedOperation":
        return cls(type=OperationType.KEY_DIFF, direction=direction, identity=identity)

    @classmethod
    def null_key(cls, *, side: OperationSide, identity: Identity) -> "TypedOperation":
        return cls(type=OperationType.NULL_KEY, side=side, identity=identity)

    @classmethod
    def duplicate_key(cls, *, side: OperationSide, identity: Identity) -> "TypedOperation":
        return cls(type=OperationType.DUPLICATE_KEY, side=side, identity=identity)

    @classmethod
    def aggregate(cls, *, side: OperationSide, aggregate: str, column: str) -> "TypedOperation":
        return cls(
            type=OperationType.AGGREGATE,
            side=side,
            aggregate_function=aggregate,
            column=column,
        )

    @classmethod
    def grouped_aggregate(
        cls,
        *,
        side: OperationSide,
        aggregate: str,
        column: str,
        group_by: tuple[str, ...],
    ) -> "TypedOperation":
        return cls(
            type=OperationType.GROUPED_AGGREGATE,
            side=side,
            aggregate_function=aggregate,
            column=column,
            group_by=group_by,
        )

    @classmethod
    def compare_aggregates(cls) -> "TypedOperation":
        return cls(type=OperationType.COMPARE_AGGREGATES)

    @classmethod
    def compare_grouped_aggregates(cls) -> "TypedOperation":
        return cls(type=OperationType.COMPARE_GROUPED_AGGREGATES)

    def to_dict(self) -> TypedOperationDict:
        operation: TypedOperationDict = {"type": self.type.value}
        if self.side is not None:
            operation["side"] = self.side.value
        if self.direction is not None:
            operation["direction"] = self.direction.value
        if self.identity is not None:
            operation["identity"] = self.identity.to_dict()
        if self.aggregate_function is not None:
            operation["aggregate"] = self.aggregate_function
        if self.column is not None:
            operation["column"] = self.column
        if self.group_by:
            operation["group_by"] = list(self.group_by)
        return operation

    def _validate(self) -> None:
        allowed_fields = _OPERATION_ALLOWED_FIELDS.get(self.type)
        if allowed_fields is None:
            raise ValueError(
                f"{self.type.value} operation is not implemented by the typed operation model"
            )

        self._reject_unexpected_fields(allowed_fields)

        if self.type in {
            OperationType.ROW_COUNT,
            OperationType.NULL_KEY,
            OperationType.DUPLICATE_KEY,
            OperationType.AGGREGATE,
            OperationType.GROUPED_AGGREGATE,
        }:
            self._require_side()

        if self.type in {
            OperationType.KEY_DIFF,
            OperationType.NULL_KEY,
            OperationType.DUPLICATE_KEY,
        }:
            self._require_identity_keys()

        if self.type is OperationType.KEY_DIFF and self.direction is None:
            raise ValueError("key_diff operation requires a direction")

        if self.type in {OperationType.AGGREGATE, OperationType.GROUPED_AGGREGATE}:
            self._require_aggregate_inputs()

        if self.type is OperationType.GROUPED_AGGREGATE and not self.group_by:
            raise ValueError("grouped_aggregate operation requires group_by fields")

    def _reject_unexpected_fields(self, allowed_fields: frozenset[str]) -> None:
        unexpected_fields = sorted(set(self._payload_fields()) - allowed_fields)
        if unexpected_fields:
            raise ValueError(
                f"{self.type.value} operation does not allow: {', '.join(unexpected_fields)}"
            )

    def _payload_fields(self) -> tuple[str, ...]:
        fields: list[str] = []
        if self.side is not None:
            fields.append("side")
        if self.direction is not None:
            fields.append("direction")
        if self.identity is not None:
            fields.append("identity")
        if self.aggregate_function is not None:
            fields.append("aggregate")
        if self.column is not None:
            fields.append("column")
        if self.group_by:
            fields.append("group_by")
        return tuple(fields)

    def _require_side(self) -> None:
        if self.side is None:
            raise ValueError(f"{self.type.value} operation requires a side")

    def _require_identity_keys(self) -> None:
        if self.identity is None or not self.identity.keys:
            raise ValueError(f"{self.type.value} operation requires at least one identity key")

    def _require_aggregate_inputs(self) -> None:
        if self.aggregate_function is None:
            raise ValueError(f"{self.type.value} operation requires an aggregate")
        if self.column is None:
            raise ValueError(f"{self.type.value} operation requires a column")


@dataclass(frozen=True, slots=True)
class CheckPlan:
    """Typed execution plan for one compiled check."""

    id: str
    operations: tuple[TypedOperation, ...]
    required_capabilities: tuple[AdapterCapability, ...]

    def to_dict(self) -> CheckPlanDict:
        return {
            "id": self.id,
            "operations": [operation.to_dict() for operation in self.operations],
            "required_capabilities": [
                capability.value for capability in self.required_capabilities
            ],
        }


@dataclass(frozen=True, slots=True)
class CompiledCheck:
    """Resolved check generated from authored checks, metrics, or check packs."""

    id: str
    name: str
    check_type: CompiledCheckType
    origin: CheckOrigin
    identity: Identity
    requirements: CheckRequirements
    plan: CheckPlan
    sampling: ResolvedSampling = ResolvedSampling()
    tolerance: object | None = None
    metric: CompiledMetric | None = None
    prerequisites: tuple[str, ...] = ()
    blocking_policy: BlockingPolicy = BlockingPolicy()
    rendering: Rendering = Rendering()
    diagnostics: tuple[Diagnostic, ...] = ()

    def to_dict(self) -> CompiledCheckDict:
        compiled_check: CompiledCheckDict = {
            "id": self.id,
            "name": self.name,
            "type": self.check_type.value,
            "origin": self.origin.to_dict(),
            "identity": self.identity.to_dict(),
            "requirements": self.requirements.to_dict(),
            "sampling": self.sampling.to_dict(),
            "tolerance": self.tolerance,
            "prerequisites": list(self.prerequisites),
            "blocking_policy": self.blocking_policy.to_dict(),
            "plan": self.plan.to_dict(),
            "rendering": self.rendering.to_dict(),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
        if self.metric is not None:
            compiled_check["metric"] = self.metric.to_dict()
        return compiled_check


@dataclass(frozen=True, slots=True)
class CompiledContractArtifact:
    """Compiled contract artifact for one authored contract."""

    artifact_type: CompiledArtifactType
    recon_version: str
    generated_at: str
    invocation_id: str
    project: CompiledProject
    contract: CompiledContractReference
    source: CompiledEndpoint
    target: CompiledEndpoint
    grain_keys: tuple[str, ...]
    columns: object | None = None
    metrics: tuple[dict[str, object], ...] = ()
    policies: CompiledContractPolicies = CompiledContractPolicies()
    diagnostics: tuple[Diagnostic, ...] = ()
    artifact_version: int = COMPILED_ARTIFACT_VERSION

    def to_dict(self) -> CompiledContractArtifactDict:
        return {
            "artifact_type": self.artifact_type.value,
            "artifact_version": self.artifact_version,
            "recon_version": self.recon_version,
            "generated_at": self.generated_at,
            "invocation_id": self.invocation_id,
            "project": self.project.to_dict(),
            "contract": self.contract.to_dict(),
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "identity": {
                "grain": {"keys": list(self.grain_keys)},
                "cdc": self.policies.cdc,
            },
            "columns": self.columns,
            "metrics": [dict(metric) for metric in self.metrics],
            "policies": self.policies.to_dict(),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class CompiledChecksArtifact:
    """Compiled checks artifact for one authored contract."""

    artifact_type: CompiledArtifactType
    recon_version: str
    generated_at: str
    invocation_id: str
    project: CompiledProject
    contract: CompiledContractReference
    checks: tuple[CompiledCheck, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    artifact_version: int = COMPILED_ARTIFACT_VERSION

    def to_dict(self) -> CompiledChecksArtifactDict:
        return {
            "artifact_type": self.artifact_type.value,
            "artifact_version": self.artifact_version,
            "recon_version": self.recon_version,
            "generated_at": self.generated_at,
            "invocation_id": self.invocation_id,
            "project": self.project.to_dict(),
            "contract": self.contract.to_dict(),
            "checks": [check.to_dict() for check in self.checks],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
