from recon_core.compiler.check_packs import (
    BASIC_EQUIVALENCE_CHECK_PACK_NAME,
    UNKNOWN_CHECK_PACK,
    VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS,
    expand_check_pack,
)
from recon_core.compiler.models import (
    AdapterCapability,
    CheckOriginKind,
    IdentityKind,
    KeyDiffDirection,
    OperationSide,
    OperationType,
)
from recon_core.diagnostics import DiagnosticSeverity


def test_basic_equivalence_expands_to_exact_checks_in_order() -> None:
    result = expand_check_pack(
        BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=("customer_id", "month"),
    )

    assert result.succeeded
    assert [check.name for check in result.checks] == [
        "row_count_diff",
        "missing_keys",
        "extra_keys",
        "null_source_keys",
        "null_target_keys",
        "duplicate_source_keys",
        "duplicate_target_keys",
    ]
    assert result.diagnostics == ()


def test_basic_equivalence_checks_have_pack_origin_and_stable_ids() -> None:
    result = expand_check_pack(
        BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=("customer_id",),
    )

    for check in result.checks:
        assert check.id == f"check.ecommerce_recon.customer_revenue.{check.name}"
        assert check.plan.id == f"plan.ecommerce_recon.customer_revenue.{check.name}"
        assert check.origin.kind is CheckOriginKind.CHECK_PACK
        assert check.origin.name == BASIC_EQUIVALENCE_CHECK_PACK_NAME
        assert check.prerequisites == ()
        assert check.blocking_policy.to_dict() == {
            "on_prerequisite_failure": "skipped",
        }
        assert check.rendering.to_dict() == {
            "status": "not_rendered",
            "sql_paths": [],
        }


def test_basic_equivalence_row_count_check_has_no_identity_requirement() -> None:
    result = expand_check_pack(
        BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=("customer_id",),
    )

    row_count = result.checks[0]

    assert row_count.name == "row_count_diff"
    assert row_count.identity.kind is IdentityKind.NONE
    assert row_count.identity.keys == ()
    assert not row_count.requirements.requires_grain_keys
    assert row_count.requirements.required_capabilities == (AdapterCapability.ROW_COUNT,)
    assert row_count.plan.to_dict()["operations"] == [
        {"type": "row_count", "side": "source"},
        {"type": "row_count", "side": "target"},
        {"type": "compare_counts"},
    ]


def test_basic_equivalence_key_diff_checks_use_grain_identity_and_directions() -> None:
    result = expand_check_pack(
        BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=("customer_id", "month"),
    )
    by_name = {check.name: check for check in result.checks}

    missing = by_name["missing_keys"]
    extra = by_name["extra_keys"]

    assert missing.identity.kind is IdentityKind.GRAIN
    assert missing.identity.keys == ("customer_id", "month")
    assert missing.requirements.requires_grain_keys
    assert not missing.requirements.requires_non_null_grain
    assert not missing.requirements.requires_unique_grain
    assert missing.requirements.required_capabilities == (AdapterCapability.KEY_DIFF,)
    assert missing.plan.operations[0].type is OperationType.KEY_DIFF
    assert missing.plan.operations[0].direction is KeyDiffDirection.SOURCE_MINUS_TARGET

    assert extra.identity.keys == ("customer_id", "month")
    assert extra.plan.operations[0].direction is KeyDiffDirection.TARGET_MINUS_SOURCE


def test_basic_equivalence_null_key_checks_are_side_specific() -> None:
    result = expand_check_pack(
        BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=("customer_id",),
    )
    by_name = {check.name: check for check in result.checks}

    source_null = by_name["null_source_keys"]
    target_null = by_name["null_target_keys"]

    assert source_null.requirements.required_capabilities == (AdapterCapability.NULL_KEY,)
    assert source_null.plan.operations[0].type is OperationType.NULL_KEY
    assert source_null.plan.operations[0].side is OperationSide.SOURCE
    assert source_null.plan.operations[0].identity == source_null.identity

    assert target_null.plan.operations[0].type is OperationType.NULL_KEY
    assert target_null.plan.operations[0].side is OperationSide.TARGET
    assert target_null.plan.operations[0].identity == target_null.identity


def test_basic_equivalence_duplicate_key_checks_are_side_specific() -> None:
    result = expand_check_pack(
        BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=("customer_id",),
    )
    by_name = {check.name: check for check in result.checks}

    source_duplicate = by_name["duplicate_source_keys"]
    target_duplicate = by_name["duplicate_target_keys"]

    assert source_duplicate.requirements.required_capabilities == (AdapterCapability.DUPLICATE_KEY,)
    assert source_duplicate.plan.operations[0].type is OperationType.DUPLICATE_KEY
    assert source_duplicate.plan.operations[0].side is OperationSide.SOURCE
    assert source_duplicate.plan.operations[0].identity == source_duplicate.identity

    assert target_duplicate.plan.operations[0].type is OperationType.DUPLICATE_KEY
    assert target_duplicate.plan.operations[0].side is OperationSide.TARGET
    assert target_duplicate.plan.operations[0].identity == target_duplicate.identity


def test_basic_equivalence_without_grain_fails_validation_without_checks() -> None:
    result = expand_check_pack(
        BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=(),
    )

    assert not result.succeeded
    assert result.checks == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "check_pack"
    assert diagnostic.resource_name == BASIC_EQUIVALENCE_CHECK_PACK_NAME
    assert "`grain.keys`" in diagnostic.message


def test_unknown_check_pack_fails_validation_without_checks() -> None:
    result = expand_check_pack(
        "recon_core.missing_pack",
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
        grain_keys=("customer_id",),
    )

    assert not result.succeeded
    assert result.checks == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == UNKNOWN_CHECK_PACK
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "check_pack"
    assert diagnostic.resource_name == "recon_core.missing_pack"
