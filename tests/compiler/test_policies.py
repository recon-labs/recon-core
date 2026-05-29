from recon_core.compiler.policies import (
    INVALID_NORMALIZATION,
    INVALID_NULL_POLICY,
    INVALID_NULL_SENTINEL,
    INVALID_REGEX_NORMALIZATION,
    INVALID_SAMPLING,
    INVALID_TOLERANCE,
    validate_normalization,
    validate_null_policy,
    validate_sampling,
    validate_tolerance,
)
from recon_core.diagnostics import DiagnosticSeverity


def test_validate_sampling_resolves_full_and_named_policy() -> None:
    full_result = validate_sampling({"default_policy": "full"})
    named_result = validate_sampling({"default_policy": "stable_hash_5_percent"})

    assert full_result.succeeded
    assert full_result.sampling.to_dict() == {"mode": "full"}
    assert named_result.succeeded
    assert named_result.sampling.to_dict() == {"policy": "stable_hash_5_percent"}


def test_validate_sampling_rejects_unsupported_shape() -> None:
    result = validate_sampling({"default_policy": "full", "policies": ["latest"]})

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [INVALID_SAMPLING]
    assert "policies" in result.diagnostics[0].message


def test_validate_tolerance_accepts_numeric_shorthand_and_absolute_object() -> None:
    shorthand_result = validate_tolerance(0.01, resource_type="metric", resource_name="revenue")
    object_result = validate_tolerance(
        {"type": "absolute", "value": 0},
        resource_type="column",
        resource_name="revenue",
    )

    assert shorthand_result.succeeded
    assert object_result.succeeded
    assert shorthand_result.diagnostics == ()
    assert object_result.diagnostics == ()


def test_validate_tolerance_rejects_negative_or_unsupported_tolerance() -> None:
    negative_result = validate_tolerance(-0.01, resource_type="metric", resource_name="revenue")
    relative_result = validate_tolerance(
        {"type": "relative", "value": 0.05},
        resource_type="metric",
        resource_name="revenue",
    )

    assert not negative_result.succeeded
    assert not relative_result.succeeded
    assert [diagnostic.code for diagnostic in negative_result.diagnostics] == [
        INVALID_TOLERANCE
    ]
    assert [diagnostic.code for diagnostic in relative_result.diagnostics] == [
        INVALID_TOLERANCE
    ]


def test_validate_null_policy_accepts_literal_and_regex_sentinels() -> None:
    result = validate_null_policy(
        {
            "treat_as_null": {
                "values": ["", "NULL"],
                "regex": ["^\\s*$"],
            }
        },
        resource_type="contract",
        resource_name="customer_revenue",
    )

    assert result.succeeded
    assert result.diagnostics == ()


def test_validate_null_policy_rejects_invalid_shape_and_sentinels() -> None:
    shape_result = validate_null_policy(
        {"empty_string_equals_null": True},
        resource_type="contract",
        resource_name="customer_revenue",
    )
    sentinel_result = validate_null_policy(
        {"treat_as_null": {"values": ["", 0]}},
        resource_type="contract",
        resource_name="customer_revenue",
    )

    assert not shape_result.succeeded
    assert not sentinel_result.succeeded
    assert [diagnostic.code for diagnostic in shape_result.diagnostics] == [
        INVALID_NULL_POLICY
    ]
    assert [diagnostic.code for diagnostic in sentinel_result.diagnostics] == [
        INVALID_NULL_SENTINEL
    ]


def test_validate_normalization_accepts_ordered_simple_and_regex_steps() -> None:
    result = validate_normalization(
        {
            "steps": [
                "trim",
                {"regex_replace": {"pattern": "\\s+-+$", "replacement": ""}},
                "lower",
            ]
        },
        resource_type="column",
        resource_name="customer_name",
    )

    assert result.succeeded
    assert result.diagnostics == ()


def test_validate_normalization_rejects_duplicate_or_incompatible_steps() -> None:
    duplicate_result = validate_normalization(
        {"steps": ["trim", "trim"]},
        resource_type="column",
        resource_name="customer_name",
    )
    incompatible_result = validate_normalization(
        {"steps": ["lower", "upper"]},
        resource_type="column",
        resource_name="customer_name",
    )

    assert not duplicate_result.succeeded
    assert not incompatible_result.succeeded
    assert [diagnostic.code for diagnostic in duplicate_result.diagnostics] == [
        INVALID_NORMALIZATION
    ]
    assert [diagnostic.code for diagnostic in incompatible_result.diagnostics] == [
        INVALID_NORMALIZATION
    ]


def test_validate_regex_profile_rejects_unsupported_regex_features() -> None:
    result = validate_normalization(
        {
            "steps": [
                {
                    "regex_replace": {
                        "pattern": "(?<=prefix)value",
                        "replacement": "",
                    }
                }
            ]
        },
        resource_type="column",
        resource_name="customer_name",
    )

    assert not result.succeeded
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code == INVALID_REGEX_NORMALIZATION
    assert result.diagnostics[0].severity is DiagnosticSeverity.ERROR
