import json

from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


def test_diagnostic_serializes_structured_context() -> None:
    diagnostic = Diagnostic(
        code="RC_PARSE_MISSING_REQUIRED_FIELD",
        severity=DiagnosticSeverity.ERROR,
        message="Contract name is required.",
        resource_type="contract",
        resource_name="customer_revenue",
        path="contracts/customer_revenue.yml",
        line=3,
        column=1,
        hint="Add a top-level name field.",
    )

    assert diagnostic.to_dict() == {
        "code": "RC_PARSE_MISSING_REQUIRED_FIELD",
        "severity": "error",
        "message": "Contract name is required.",
        "resource_type": "contract",
        "resource_name": "customer_revenue",
        "path": "contracts/customer_revenue.yml",
        "line": 3,
        "column": 1,
        "hint": "Add a top-level name field.",
    }


def test_diagnostic_json_has_string_severity() -> None:
    diagnostic = Diagnostic(
        code="RC_PARSE_INVALID_YAML",
        severity=DiagnosticSeverity.ERROR,
        message="YAML could not be parsed.",
    )

    payload = json.loads(json.dumps(diagnostic.to_dict()))

    assert payload["severity"] == "error"
