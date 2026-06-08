from typing import Any

from recon_core.adapters import (
    AdapterCapabilities,
    CapabilitySupport,
    validate_required_capabilities,
)


def test_full_support_satisfies_required_capability() -> None:
    capabilities = AdapterCapabilities({"row_count": CapabilitySupport.FULL})

    assert capabilities.satisfies("row_count")
    assert (
        validate_required_capabilities(
            adapter_type="duckdb",
            capabilities=capabilities,
            required_capabilities=("row_count",),
        )
        == ()
    )


def test_non_full_support_states_do_not_satisfy_required_capability() -> None:
    for support in (
        CapabilitySupport.UNKNOWN,
        CapabilitySupport.UNSUPPORTED,
        CapabilitySupport.NOT_IMPLEMENTED,
        CapabilitySupport.VERSIONED,
    ):
        capabilities = AdapterCapabilities({"row_count": support})

        diagnostics = validate_required_capabilities(
            adapter_type="duckdb",
            capabilities=capabilities,
            required_capabilities=("row_count",),
        )

        assert not capabilities.satisfies("row_count")
        assert [diagnostic.code for diagnostic in diagnostics] == [
            "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
        ]
        assert support.value in diagnostics[0].message


def test_missing_capability_defaults_to_unknown() -> None:
    capabilities = AdapterCapabilities({})

    diagnostics = validate_required_capabilities(
        adapter_type="duckdb",
        capabilities=capabilities,
        required_capabilities=("row_count",),
    )

    assert capabilities.support_for("row_count") is CapabilitySupport.UNKNOWN
    assert not capabilities.satisfies("row_count")
    assert diagnostics[0].message.endswith("support state `unknown`.")


def test_invalid_capability_support_state_reports_diagnostic() -> None:
    invalid_support: dict[str, Any] = {"row_count": "wat"}
    capabilities = AdapterCapabilities(invalid_support)

    diagnostics = validate_required_capabilities(
        adapter_type="duckdb",
        capabilities=capabilities,
        required_capabilities=("row_count",),
    )

    assert not capabilities.satisfies("row_count")
    assert [diagnostic.code for diagnostic in diagnostics] == ["RC_ADAPTER_CAPABILITY_UNSUPPORTED"]
    assert "invalid" in diagnostics[0].message
