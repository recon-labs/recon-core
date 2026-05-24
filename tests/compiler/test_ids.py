import pytest

from recon_core.compiler.ids import (
    build_check_id,
    build_contract_id,
    build_plan_id,
    is_valid_stable_id_part,
)


def test_build_contract_id_uses_public_stable_shape() -> None:
    assert build_contract_id("ecommerce_recon", "customer_revenue") == (
        "contract.ecommerce_recon.customer_revenue"
    )


def test_build_check_id_uses_public_stable_shape() -> None:
    assert build_check_id("ecommerce_recon", "customer_revenue", "row_count_diff") == (
        "check.ecommerce_recon.customer_revenue.row_count_diff"
    )


def test_build_plan_id_uses_public_stable_shape() -> None:
    assert build_plan_id("ecommerce_recon", "customer_revenue", "row_count_diff") == (
        "plan.ecommerce_recon.customer_revenue.row_count_diff"
    )


def test_is_valid_stable_id_part_matches_public_id_rules() -> None:
    assert is_valid_stable_id_part("customer_revenue")
    assert is_valid_stable_id_part("_customer_revenue")
    assert not is_valid_stable_id_part("customer-revenue")
    assert not is_valid_stable_id_part("1_customer_revenue")


@pytest.mark.parametrize(
    ("builder", "parts"),
    [
        (build_contract_id, ("bad-project", "customer_revenue")),
        (build_contract_id, ("ecommerce_recon", "customer revenue")),
        (build_check_id, ("ecommerce_recon", "customer_revenue", "")),
        (build_plan_id, ("ecommerce_recon", "customer_revenue", "row.count")),
    ],
)
def test_stable_id_builders_reject_invalid_parts(builder: object, parts: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="Stable ID parts"):
        builder(*parts)  # type: ignore[operator]
