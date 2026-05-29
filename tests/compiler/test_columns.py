from recon_core.compiler.columns import (
    DUPLICATE_COLUMN_NAME,
    INCOMPATIBLE_COLUMN_TYPE,
    INVALID_COLUMN_DECLARATION,
    INVALID_COLUMN_SELECTION,
    ColumnCategory,
    validate_columns,
)
from recon_core.compiler.policies import INVALID_NORMALIZATION, INVALID_NULL_POLICY
from recon_core.diagnostics import DiagnosticSeverity


def test_validate_columns_accepts_supported_categories_and_shorthand() -> None:
    result = validate_columns(
        {
            "exact": ["status"],
            "numeric": [{"name": "revenue", "tolerance": 0.01}],
            "timestamp": ["updated_at"],
            "string": [{"name": "customer_name", "normalization": {"steps": ["trim"]}}],
        }
    )

    assert result.succeeded
    assert result.diagnostics == ()
    assert result.registry.has_explicit_surface
    assert result.registry.names == frozenset({"status", "revenue", "updated_at", "customer_name"})
    assert result.registry.declaration_for("revenue").category is ColumnCategory.NUMERIC
    assert result.registry.declaration_for("status").category is ColumnCategory.EXACT


def test_validate_columns_allows_no_columns_block() -> None:
    result = validate_columns(None)

    assert result.succeeded
    assert not result.registry.has_explicit_surface
    assert result.registry.names == frozenset()


def test_validate_columns_rejects_unknown_category() -> None:
    result = validate_columns({"boolean": ["is_active"]})

    assert not result.succeeded
    assert result.registry.names == frozenset()
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == INVALID_COLUMN_DECLARATION
    assert result.diagnostics[0].severity is DiagnosticSeverity.ERROR
    assert "boolean" in result.diagnostics[0].message


def test_validate_columns_rejects_unknown_column_field() -> None:
    result = validate_columns({"numeric": [{"name": "revenue", "scale": 2}]})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_COLUMN_DECLARATION]
    assert "scale" in result.diagnostics[0].message


def test_validate_columns_rejects_invalid_description_shape() -> None:
    result = validate_columns({"numeric": [{"name": "revenue", "description": {"bad": True}}]})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_COLUMN_DECLARATION]
    assert "description" in result.diagnostics[0].message


def test_validate_columns_rejects_current_unsupported_timezone_policy() -> None:
    result = validate_columns({"timestamp": [{"name": "updated_at", "timezone": "UTC"}]})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_COLUMN_DECLARATION]
    assert "timezone" in result.diagnostics[0].message


def test_validate_columns_rejects_duplicate_declared_names() -> None:
    result = validate_columns({"exact": ["revenue"], "numeric": ["revenue"]})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [DUPLICATE_COLUMN_NAME]
    assert result.diagnostics[0].resource_type == "column"
    assert result.diagnostics[0].resource_name == "revenue"


def test_validate_columns_rejects_wildcard_column_declaration() -> None:
    result = validate_columns({"include": "*"})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_COLUMN_SELECTION]
    assert "all-column" in result.diagnostics[0].message


def test_validate_columns_rejects_tolerance_on_non_numeric_column() -> None:
    result = validate_columns({"exact": [{"name": "status", "tolerance": 0.01}]})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INCOMPATIBLE_COLUMN_TYPE]
    assert result.diagnostics[0].resource_name == "status"


def test_validate_columns_rejects_invalid_null_policy_shape() -> None:
    result = validate_columns(
        {"string": [{"name": "middle_name", "nulls": {"empty_string_equals_null": True}}]}
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_NULL_POLICY]
    assert result.diagnostics[0].resource_name == "middle_name"


def test_validate_columns_rejects_normalization_on_non_string_column() -> None:
    result = validate_columns({"numeric": [{"name": "revenue", "normalization": {"steps": []}}]})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INCOMPATIBLE_COLUMN_TYPE]
    assert result.diagnostics[0].resource_name == "revenue"


def test_validate_columns_rejects_invalid_normalization_shape() -> None:
    result = validate_columns(
        {"string": [{"name": "customer_name", "normalization": {"steps": ["trim", "trim"]}}]}
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_NORMALIZATION]
    assert result.diagnostics[0].resource_name == "customer_name"
