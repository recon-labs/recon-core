from recon_core.compiler.cdc import INVALID_CDC_KEYS, validate_cdc_policy
from recon_core.diagnostics import DiagnosticSeverity


def test_validate_cdc_policy_accepts_explicit_keys_and_same_as_grain() -> None:
    explicit_result = validate_cdc_policy({"keys": ["source_order_id"]}, grain_keys=())
    same_as_result = validate_cdc_policy(
        {"keys": {"same_as": "grain"}},
        grain_keys=("order_id",),
    )

    assert explicit_result.succeeded
    assert explicit_result.diagnostics == ()
    assert same_as_result.succeeded
    assert same_as_result.diagnostics == ()


def test_validate_cdc_policy_allows_absent_keys_without_cdc_checks() -> None:
    result = validate_cdc_policy(
        {"mode": "upsert", "timestamp_column": "updated_at"},
        grain_keys=(),
    )

    assert result.succeeded
    assert result.diagnostics == ()


def test_validate_cdc_policy_rejects_invalid_keys_shape() -> None:
    result = validate_cdc_policy({"keys": "order_id"}, grain_keys=())

    assert not result.succeeded
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == INVALID_CDC_KEYS
    assert result.diagnostics[0].severity is DiagnosticSeverity.ERROR
    assert "cdc.keys" in result.diagnostics[0].message


def test_validate_cdc_policy_rejects_empty_keys() -> None:
    result = validate_cdc_policy({"keys": []}, grain_keys=())

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_CDC_KEYS]
    assert "non-empty" in result.diagnostics[0].message


def test_validate_cdc_policy_rejects_same_as_grain_without_grain_keys() -> None:
    result = validate_cdc_policy({"keys": {"same_as": "grain"}}, grain_keys=())

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_CDC_KEYS]
    assert "grain.keys" in result.diagnostics[0].message
