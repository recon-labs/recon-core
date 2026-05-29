"""CDC declaration validation for compiler-owned behavior."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from recon_core.compiler.validation import CompilerDiagnosticContext
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

CDC_CONFIG_REQUIRED = "RC_VALIDATE_CDC_CONFIG_REQUIRED"


@dataclass(frozen=True, slots=True)
class CdcValidationResult:
    """Validation diagnostics for authored CDC declaration fields."""

    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )


def validate_cdc_policy(
    cdc: Mapping[str, object] | None,
    *,
    grain_keys: Sequence[str],
    context: CompilerDiagnosticContext | None = None,
) -> CdcValidationResult:
    """Validate current CDC declaration fields without implementing CDC execution."""
    if cdc is None or "keys" not in cdc:
        return CdcValidationResult()

    diagnostic_context = context or CompilerDiagnosticContext(resource_type="contract")
    keys = cdc["keys"]
    if isinstance(keys, Mapping):
        return CdcValidationResult(
            diagnostics=tuple(_validate_cdc_same_as_keys(keys, grain_keys, diagnostic_context))
        )

    if isinstance(keys, Sequence) and not isinstance(keys, str):
        if all(isinstance(key, str) and key for key in keys):
            return CdcValidationResult()
        return CdcValidationResult(
            diagnostics=(
                _cdc_config_diagnostic(
                    diagnostic_context,
                    "`cdc.keys` must contain only non-empty strings.",
                ),
            )
        )

    return CdcValidationResult(
        diagnostics=(
            _cdc_config_diagnostic(
                diagnostic_context,
                "`cdc.keys` must be a list of non-empty strings or `{same_as: grain}`.",
            ),
        )
    )


def _validate_cdc_same_as_keys(
    keys: Mapping[object, object],
    grain_keys: Sequence[str],
    context: CompilerDiagnosticContext,
) -> tuple[Diagnostic, ...]:
    if set(keys) != {"same_as"} or keys.get("same_as") != "grain":
        return (
            _cdc_config_diagnostic(
                context,
                "`cdc.keys` mapping currently supports only `{same_as: grain}`.",
            ),
        )

    if not grain_keys:
        return (
            _cdc_config_diagnostic(
                context,
                "`cdc.keys.same_as: grain` requires contract `grain.keys`.",
            ),
        )

    return ()


def _cdc_config_diagnostic(context: CompilerDiagnosticContext, message: str) -> Diagnostic:
    return context.error(
        code=CDC_CONFIG_REQUIRED,
        message=message,
        hint="Use explicit `cdc.keys` or `cdc.keys: {same_as: grain}` when CDC keys are declared.",
    )
