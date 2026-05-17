import pytest

from recon_core.diagnostics import DiagnosticSeverity
from recon_core.services import CompileService, ParseService, RunService
from recon_core.services.results import ExitCategory


@pytest.mark.parametrize(
    ("service_cls", "command_name"),
    [
        (ParseService, "parse"),
        (CompileService, "compile"),
        (RunService, "run"),
    ],
)
def test_command_service_stubs_return_structured_not_implemented_result(
    service_cls: type[ParseService | CompileService | RunService],
    command_name: str,
) -> None:
    result = service_cls().execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == f"recon {command_name} is not implemented yet."
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == "RC_RUNTIME_NOT_IMPLEMENTED"
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.message == result.message
    assert diagnostic.hint == f"Implement {service_cls.__name__} in a later milestone."
