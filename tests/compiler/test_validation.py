import pytest

from recon_core.compiler.validation import (
    CompilerDiagnosticContext,
    contract_diagnostic_context,
    with_default_diagnostic_path,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import AuthoredContract, AuthoredEndpoint
from recon_core.parser.models import SourceLocation


def test_compiler_diagnostic_context_builds_error_diagnostic() -> None:
    context = CompilerDiagnosticContext(
        resource_type="contract",
        resource_name="customer_revenue",
        path="contracts/customer_revenue.yml",
    )

    diagnostic = context.error(
        code="RC_VALIDATE_INVALID_SAMPLING",
        message="Contract `sampling.default_policy` must be valid.",
        hint="Use `sampling: {default_policy: full}`.",
    )

    assert diagnostic == Diagnostic(
        code="RC_VALIDATE_INVALID_SAMPLING",
        severity=DiagnosticSeverity.ERROR,
        message="Contract `sampling.default_policy` must be valid.",
        resource_type="contract",
        resource_name="customer_revenue",
        path="contracts/customer_revenue.yml",
        hint="Use `sampling: {default_policy: full}`.",
    )


def test_compiler_diagnostic_context_allows_nested_resource_override() -> None:
    context = CompilerDiagnosticContext(
        resource_type="contract",
        resource_name="customer_revenue",
        path="contracts/customer_revenue.yml",
    )

    diagnostic = context.error(
        code="RC_COMPILE_UNSUPPORTED_CHECK_PACK_CONFIG",
        message="Check-pack invocation has unsupported fields.",
        resource_type="check_pack",
        resource_name="recon_core.basic_equivalence",
    )

    assert diagnostic.resource_type == "check_pack"
    assert diagnostic.resource_name == "recon_core.basic_equivalence"
    assert diagnostic.path == "contracts/customer_revenue.yml"


def test_compiler_diagnostic_context_rejects_non_compiler_code_family() -> None:
    context = CompilerDiagnosticContext(
        resource_type="contract",
        resource_name="customer_revenue",
        path="contracts/customer_revenue.yml",
    )

    with pytest.raises(ValueError, match="RC_COMPILE_\\* or RC_VALIDATE_\\*"):
        context.error(
            code="RC_PARSE_UNKNOWN_FIELD",
            message="Unknown contract field.",
        )


def test_contract_diagnostic_context_uses_authored_contract_location() -> None:
    contract = _contract()

    context = contract_diagnostic_context(contract)

    assert context == CompilerDiagnosticContext(
        resource_type="contract",
        resource_name="customer_revenue",
        path="contracts/customer_revenue.yml",
    )


def test_with_default_diagnostic_path_preserves_existing_paths() -> None:
    diagnostics = (
        Diagnostic(
            code="RC_COMPILE_UNKNOWN_CHECK_PACK",
            severity=DiagnosticSeverity.ERROR,
            message="Unknown check pack.",
            path="packs/core.yml",
        ),
        Diagnostic(
            code="RC_COMPILE_EMPTY_CHECK_PACK",
            severity=DiagnosticSeverity.ERROR,
            message="Check pack expanded to no checks.",
        ),
    )

    updated = with_default_diagnostic_path(diagnostics, "contracts/customer_revenue.yml")

    assert updated[0].path == "packs/core.yml"
    assert updated[1].path == "contracts/customer_revenue.yml"


def _contract() -> AuthoredContract:
    return AuthoredContract(
        name="customer_revenue",
        version=1,
        source=AuthoredEndpoint(connection="legacy", relation="qa.customer_source"),
        target=AuthoredEndpoint(connection="warehouse", relation="qa.customer_target"),
        checks={"use": ["recon_core.basic_equivalence"]},
        source_location=SourceLocation(path="contracts/customer_revenue.yml"),
    )
