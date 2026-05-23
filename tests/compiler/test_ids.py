import pytest

from recon_core.compiler.ids import (
    build_check_id,
    build_contract_id,
    build_plan_id,
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
