from pathlib import Path

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.parser import (
    AuthoredContract,
    AuthoredEndpoint,
    ResourceFile,
    ResourceType,
    parse_contract_resource,
)


def make_resource_file(
    tmp_path: Path, relative_path: str = "contracts/customer.yml"
) -> ResourceFile:
    path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: placeholder\n", encoding="utf-8")
    return ResourceFile(
        path=path,
        relative_path=relative_path,
        resource_type=ResourceType.CONTRACT,
        checksum="abc123",
    )


def single_contract_data() -> dict[str, object]:
    return {
        "version": 1,
        "name": "customer_revenue",
        "description": "Customer revenue reconciliation.",
        "source": {
            "connection": "legacy",
            "relation": "qa.v_customer_revenue_compare",
        },
        "target": {
            "connection": "warehouse",
            "relation": "qa.v_customer_revenue_compare",
        },
        "grain": {"keys": ["customer_id", "month"]},
        "columns": {
            "numeric": [
                {
                    "name": "revenue",
                    "tolerance": 0.01,
                    "future_nested_setting": True,
                }
            ]
        },
        "metrics": [
            {
                "name": "revenue_by_month",
                "type": "sum",
                "column": "revenue",
                "group_by": ["month"],
            }
        ],
        "checks": {"use": ["recon_core.basic_equivalence"]},
        "sampling": {"default_policy": "full"},
        "schema": {"ignore_target_columns": ["_loaded_at"]},
        "cdc": {"mode": "upsert", "timestamp_column": "updated_at"},
        "evidence": {"level": "detailed", "store_failures": True},
        "owners": {"engineering": "data_platform"},
        "tags": ["finance", "critical"],
    }


def test_parse_contract_resource_parses_single_contract(tmp_path: Path) -> None:
    resource_file = make_resource_file(tmp_path)

    result = parse_contract_resource(resource_file, single_contract_data())

    assert result.succeeded
    assert result.diagnostics == ()
    assert result.contracts == (
        AuthoredContract(
            name="customer_revenue",
            version=1,
            source=AuthoredEndpoint(
                connection="legacy",
                relation="qa.v_customer_revenue_compare",
            ),
            target=AuthoredEndpoint(
                connection="warehouse",
                relation="qa.v_customer_revenue_compare",
            ),
            description="Customer revenue reconciliation.",
            grain={"keys": ["customer_id", "month"]},
            columns={
                "numeric": [
                    {
                        "name": "revenue",
                        "tolerance": 0.01,
                        "future_nested_setting": True,
                    }
                ]
            },
            metrics=(
                {
                    "name": "revenue_by_month",
                    "type": "sum",
                    "column": "revenue",
                    "group_by": ["month"],
                },
            ),
            checks={"use": ["recon_core.basic_equivalence"]},
            sampling={"default_policy": "full"},
            schema={"ignore_target_columns": ["_loaded_at"]},
            cdc={"mode": "upsert", "timestamp_column": "updated_at"},
            evidence={"level": "detailed", "store_failures": True},
            owners={"engineering": "data_platform"},
            tags=("finance", "critical"),
            source_location=result.contracts[0].source_location,
        ),
    )
    assert result.contracts[0].source_location.path == "contracts/customer.yml"


def test_parse_contract_resource_supports_query_endpoints(tmp_path: Path) -> None:
    resource_file = make_resource_file(tmp_path)
    data = single_contract_data()
    data["source"] = {"connection": "legacy", "query": "select * from source_view"}
    data["target"] = {"connection": "warehouse", "query": "select * from target_view"}

    result = parse_contract_resource(resource_file, data)

    assert result.succeeded
    assert result.contracts[0].source.query == "select * from source_view"
    assert result.contracts[0].source.relation is None
    assert result.contracts[0].target.query == "select * from target_view"
    assert result.contracts[0].target.relation is None


def test_parse_contract_resource_parses_simple_multi_contract_file(
    tmp_path: Path,
) -> None:
    resource_file = make_resource_file(tmp_path, "contracts/grouped.yml")
    data = {
        "version": 1,
        "contracts": [
            {
                "name": "customer_revenue",
                "source": {"connection": "legacy", "relation": "qa.customer_source"},
                "target": {"connection": "warehouse", "relation": "qa.customer_target"},
                "checks": {"use": ["recon_core.basic_equivalence"]},
            },
            {
                "name": "orders",
                "source": {"connection": "legacy", "relation": "qa.orders_source"},
                "target": {"connection": "warehouse", "relation": "qa.orders_target"},
                "checks": {"use": ["recon_core.basic_equivalence"]},
                "tags": ["cdc"],
            },
        ],
    }

    result = parse_contract_resource(resource_file, data)

    assert result.succeeded
    assert [contract.name for contract in result.contracts] == ["customer_revenue", "orders"]
    assert [contract.version for contract in result.contracts] == [1, 1]
    assert result.contracts[1].tags == ("cdc",)


def test_parse_contract_resource_reports_non_mapping_top_level(tmp_path: Path) -> None:
    resource_file = make_resource_file(tmp_path)

    result = parse_contract_resource(resource_file, ["customer_revenue"])

    assert not result.succeeded
    assert result.contracts == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_INVALID_CONTRACT"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "contract"
    assert diagnostic.path == "contracts/customer.yml"
    assert "top-level mapping" in diagnostic.message


def test_parse_contract_resource_reports_missing_required_fields(tmp_path: Path) -> None:
    resource_file = make_resource_file(tmp_path)

    result = parse_contract_resource(
        resource_file,
        {
            "version": 1,
            "name": "customer_revenue",
        },
    )

    assert not result.succeeded
    assert result.contracts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD",
        "RC_PARSE_MISSING_REQUIRED_FIELD",
        "RC_PARSE_MISSING_REQUIRED_FIELD",
    ]
    assert [diagnostic.message for diagnostic in result.diagnostics] == [
        "Missing required contract field: source",
        "Missing required contract field: target",
        "Missing required contract field: checks",
    ]


def test_parse_contract_resource_reports_unknown_top_level_field(tmp_path: Path) -> None:
    resource_file = make_resource_file(tmp_path)
    data = single_contract_data()
    data["unexpected"] = True

    result = parse_contract_resource(resource_file, data)

    assert not result.succeeded
    assert result.contracts == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_PARSE_UNKNOWN_FIELD"
    assert diagnostic.path == "contracts/customer.yml"
    assert "unexpected" in diagnostic.message


def test_parse_contract_resource_reports_invalid_endpoint_shape(tmp_path: Path) -> None:
    resource_file = make_resource_file(tmp_path)
    data = single_contract_data()
    data["source"] = {
        "connection": "legacy",
        "relation": "qa.customer_source",
        "query": "select * from qa.customer_source",
    }
    data["target"] = {"relation": "qa.customer_target"}

    result = parse_contract_resource(resource_file, data)

    assert not result.succeeded
    assert result.contracts == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_INVALID_ENDPOINT",
        "RC_PARSE_INVALID_ENDPOINT",
    ]
    assert "exactly one" in result.diagnostics[0].message
    assert "connection" in result.diagnostics[1].message


def test_parse_contract_resource_reports_multi_contract_mixed_shape(
    tmp_path: Path,
) -> None:
    resource_file = make_resource_file(tmp_path)
    data = single_contract_data()
    data["contracts"] = []

    result = parse_contract_resource(resource_file, data)

    assert not result.succeeded
    assert result.contracts == ()
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "RC_PARSE_INVALID_CONTRACT"
    assert "cannot mix `contracts`" in result.diagnostics[0].message


def test_parse_contract_resource_reports_invalid_multi_contract_entries(
    tmp_path: Path,
) -> None:
    resource_file = make_resource_file(tmp_path, "contracts/grouped.yml")

    result = parse_contract_resource(
        resource_file,
        {
            "version": 1,
            "contracts": ["customer_revenue"],
        },
    )

    assert not result.succeeded
    assert result.contracts == ()
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == "RC_PARSE_INVALID_CONTRACT"
    assert "must be a mapping" in result.diagnostics[0].message


def test_parse_contract_resource_preserves_valid_multi_contract_entries_with_diagnostics(
    tmp_path: Path,
) -> None:
    resource_file = make_resource_file(tmp_path, "contracts/grouped.yml")

    result = parse_contract_resource(
        resource_file,
        {
            "version": 1,
            "contracts": [
                {
                    "name": "customer_revenue",
                    "source": {"connection": "legacy", "relation": "qa.customer_source"},
                    "target": {"connection": "warehouse", "relation": "qa.customer_target"},
                    "checks": {"use": ["recon_core.basic_equivalence"]},
                },
                {
                    "name": "broken_contract",
                    "source": {"connection": "legacy", "relation": "qa.broken_source"},
                    "target": {"connection": "warehouse", "relation": "qa.broken_target"},
                },
            ],
        },
    )

    assert not result.succeeded
    assert [contract.name for contract in result.contracts] == ["customer_revenue"]
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]


def test_authored_contract_serializes_summary_dict(tmp_path: Path) -> None:
    resource_file = make_resource_file(tmp_path)
    result = parse_contract_resource(resource_file, single_contract_data())

    assert result.contracts[0].to_summary_dict() == {
        "name": "customer_revenue",
        "version": 1,
        "path": "contracts/customer.yml",
        "tags": ["finance", "critical"],
        "source": {
            "connection": "legacy",
            "relation": "qa.v_customer_revenue_compare",
            "query": None,
        },
        "target": {
            "connection": "warehouse",
            "relation": "qa.v_customer_revenue_compare",
            "query": None,
        },
    }
