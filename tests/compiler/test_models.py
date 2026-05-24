import json

import pytest

from recon_core.compiler import Rendering
from recon_core.compiler.models import (
    AdapterCapability,
    CheckPlan,
    Identity,
    IdentityKind,
    OperationSide,
    OperationType,
    TypedOperation,
)


def test_null_key_operation_serializes_required_side_and_identity() -> None:
    identity = Identity(kind=IdentityKind.GRAIN, keys=("customer_id", "month"))
    operation = TypedOperation.null_key(side=OperationSide.SOURCE, identity=identity)

    assert operation.to_dict() == {
        "type": "null_key",
        "side": "source",
        "identity": {
            "kind": "grain",
            "keys": ["customer_id", "month"],
        },
    }


def test_null_key_operation_requires_identity_keys() -> None:
    with pytest.raises(ValueError, match="requires at least one identity key"):
        TypedOperation.null_key(
            side=OperationSide.SOURCE,
            identity=Identity(kind=IdentityKind.GRAIN, keys=()),
        )


def test_compare_aggregate_operations_are_distinct_public_types() -> None:
    assert OperationType.COMPARE_AGGREGATES.value == "compare_aggregates"
    assert OperationType.COMPARE_GROUPED_AGGREGATES.value == "compare_grouped_aggregates"
    assert OperationType.COMPARE_AGGREGATES is not OperationType.COMPARE_GROUPED_AGGREGATES


def test_check_plan_serializes_operations_and_capabilities_deterministically() -> None:
    plan = CheckPlan(
        id="plan.ecommerce_recon.customer_revenue.row_count_diff",
        operations=(
            TypedOperation.row_count(side=OperationSide.SOURCE),
            TypedOperation.row_count(side=OperationSide.TARGET),
            TypedOperation.compare_counts(),
        ),
        required_capabilities=(AdapterCapability.ROW_COUNT,),
    )

    assert plan.to_dict() == {
        "id": "plan.ecommerce_recon.customer_revenue.row_count_diff",
        "operations": [
            {"type": "row_count", "side": "source"},
            {"type": "row_count", "side": "target"},
            {"type": "compare_counts"},
        ],
        "required_capabilities": ["row_count"],
    }


def test_rendering_model_is_exported_from_compiler_package() -> None:
    assert Rendering().to_dict() == {
        "status": "not_rendered",
        "sql_paths": [],
    }


def test_capability_names_are_public_strings_in_json() -> None:
    payload = json.loads(json.dumps({"capability": AdapterCapability.NULL_KEY.value}))

    assert payload["capability"] == "null_key"
