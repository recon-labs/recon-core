from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.services.results import ExitCategory, ServiceResult, exit_code_for


def test_exit_categories_map_to_documented_codes() -> None:
    assert exit_code_for(ExitCategory.SUCCESS) == 0
    assert exit_code_for(ExitCategory.CHECK_FAILURE) == 1
    assert exit_code_for(ExitCategory.VALIDATION_ERROR) == 2
    assert exit_code_for(ExitCategory.RUNTIME_ERROR) == 3
    assert exit_code_for(ExitCategory.CONFIGURATION_ERROR) == 4


def test_service_result_preserves_diagnostics() -> None:
    diagnostic = Diagnostic(
        code="RC_CONFIG_MISSING_PROJECT",
        severity=DiagnosticSeverity.ERROR,
        message="Could not find recon_project.yml.",
        hint="Run the command from a Recon project or pass --project-dir later.",
    )

    result = ServiceResult(
        exit_category=ExitCategory.CONFIGURATION_ERROR,
        message="Project configuration failed.",
        diagnostics=(diagnostic,),
    )

    assert not result.succeeded
    assert result.to_dict() == {
        "exit_category": "configuration_error",
        "exit_code": 4,
        "message": "Project configuration failed.",
        "diagnostics": [diagnostic.to_dict()],
    }


def test_success_result_defaults_to_empty_diagnostics() -> None:
    result = ServiceResult.success(message="Ready.")

    assert result.succeeded
    assert result.exit_category is ExitCategory.SUCCESS
    assert result.diagnostics == ()
    assert result.to_dict() == {
        "exit_category": "success",
        "exit_code": 0,
        "message": "Ready.",
        "diagnostics": [],
    }
