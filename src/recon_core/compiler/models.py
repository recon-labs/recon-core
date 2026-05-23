"""Compiler models for typed check plans and public compiler catalog values."""

from dataclasses import dataclass
from enum import StrEnum
from typing import NotRequired, TypedDict

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


class IdentityKind(StrEnum):
    """Identity role used by a check or operation."""

    NONE = "none"
    GRAIN = "grain"
    CDC = "cdc"


class RenderingStatus(StrEnum):
    """SQL rendering status for a compiled check."""

    NOT_RENDERED = "not_rendered"
    RENDERED = "rendered"
    DEFERRED = "deferred"
    UNSUPPORTED = "unsupported"


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
