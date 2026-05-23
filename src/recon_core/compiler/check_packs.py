"""Built-in check-pack expansion."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from recon_core.compiler.ids import build_check_id, build_plan_id
from recon_core.compiler.models import (
    AdapterCapability,
    CheckOrigin,
    CheckOriginKind,
    CheckPlan,
    CheckRequirements,
    CompiledCheck,
    CompiledCheckType,
    Identity,
    IdentityKind,
    KeyDiffDirection,
    OperationSide,
    TypedOperation,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

BASIC_EQUIVALENCE_CHECK_PACK_NAME = "recon_core.basic_equivalence"
UNKNOWN_CHECK_PACK = "RC_COMPILE_UNKNOWN_CHECK_PACK"
VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS = "RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS"


class _SideKeyOperationBuilder(Protocol):
    def __call__(self, *, side: OperationSide, identity: Identity) -> TypedOperation: ...


@dataclass(frozen=True, slots=True)
class CheckPackExpansionResult:
    """Result of expanding one check pack."""

    checks: tuple[CompiledCheck, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )


def expand_check_pack(
    check_pack_name: str,
    *,
    project_name: str,
    contract_name: str,
    grain_keys: Sequence[str],
) -> CheckPackExpansionResult:
    """Expand a known check pack into explicit compiled checks."""
    if check_pack_name != BASIC_EQUIVALENCE_CHECK_PACK_NAME:
        return CheckPackExpansionResult(
            diagnostics=(_unknown_check_pack_diagnostic(check_pack_name),)
        )

    return expand_basic_equivalence(
        project_name=project_name,
        contract_name=contract_name,
        grain_keys=grain_keys,
    )


def expand_basic_equivalence(
    *,
    project_name: str,
    contract_name: str,
    grain_keys: Sequence[str],
) -> CheckPackExpansionResult:
    """Expand `recon_core.basic_equivalence` into explicit key safety checks."""
    normalized_grain_keys = tuple(grain_keys)
    if not normalized_grain_keys:
        return CheckPackExpansionResult(
            diagnostics=(_basic_equivalence_requires_grain_diagnostic(),)
        )

    identity = Identity(kind=IdentityKind.GRAIN, keys=normalized_grain_keys)
    return CheckPackExpansionResult(
        checks=(
            _row_count_diff(project_name, contract_name),
            _key_diff_check(
                project_name,
                contract_name,
                CompiledCheckType.MISSING_KEYS,
                identity,
                KeyDiffDirection.SOURCE_MINUS_TARGET,
            ),
            _key_diff_check(
                project_name,
                contract_name,
                CompiledCheckType.EXTRA_KEYS,
                identity,
                KeyDiffDirection.TARGET_MINUS_SOURCE,
            ),
            _side_key_check(
                project_name,
                contract_name,
                CompiledCheckType.NULL_SOURCE_KEYS,
                identity,
                OperationSide.SOURCE,
                AdapterCapability.NULL_KEY,
                TypedOperation.null_key,
            ),
            _side_key_check(
                project_name,
                contract_name,
                CompiledCheckType.NULL_TARGET_KEYS,
                identity,
                OperationSide.TARGET,
                AdapterCapability.NULL_KEY,
                TypedOperation.null_key,
            ),
            _side_key_check(
                project_name,
                contract_name,
                CompiledCheckType.DUPLICATE_SOURCE_KEYS,
                identity,
                OperationSide.SOURCE,
                AdapterCapability.DUPLICATE_KEY,
                TypedOperation.duplicate_key,
            ),
            _side_key_check(
                project_name,
                contract_name,
                CompiledCheckType.DUPLICATE_TARGET_KEYS,
                identity,
                OperationSide.TARGET,
                AdapterCapability.DUPLICATE_KEY,
                TypedOperation.duplicate_key,
            ),
        )
    )


def _row_count_diff(project_name: str, contract_name: str) -> CompiledCheck:
    check_type = CompiledCheckType.ROW_COUNT_DIFF
    capability = AdapterCapability.ROW_COUNT
    return _compiled_check(
        project_name,
        contract_name,
        check_type,
        identity=Identity(kind=IdentityKind.NONE),
        requirements=CheckRequirements(required_capabilities=(capability,)),
        plan=CheckPlan(
            id=build_plan_id(project_name, contract_name, check_type.value),
            operations=(
                TypedOperation.row_count(side=OperationSide.SOURCE),
                TypedOperation.row_count(side=OperationSide.TARGET),
                TypedOperation.compare_counts(),
            ),
            required_capabilities=(capability,),
        ),
    )


def _key_diff_check(
    project_name: str,
    contract_name: str,
    check_type: CompiledCheckType,
    identity: Identity,
    direction: KeyDiffDirection,
) -> CompiledCheck:
    capability = AdapterCapability.KEY_DIFF
    return _compiled_check(
        project_name,
        contract_name,
        check_type,
        identity=identity,
        requirements=_grain_check_requirements(capability),
        plan=CheckPlan(
            id=build_plan_id(project_name, contract_name, check_type.value),
            operations=(TypedOperation.key_diff(direction=direction, identity=identity),),
            required_capabilities=(capability,),
        ),
    )


def _side_key_check(
    project_name: str,
    contract_name: str,
    check_type: CompiledCheckType,
    identity: Identity,
    side: OperationSide,
    capability: AdapterCapability,
    operation_builder: _SideKeyOperationBuilder,
) -> CompiledCheck:
    return _compiled_check(
        project_name,
        contract_name,
        check_type,
        identity=identity,
        requirements=_grain_check_requirements(capability),
        plan=CheckPlan(
            id=build_plan_id(project_name, contract_name, check_type.value),
            operations=(operation_builder(side=side, identity=identity),),
            required_capabilities=(capability,),
        ),
    )


def _compiled_check(
    project_name: str,
    contract_name: str,
    check_type: CompiledCheckType,
    *,
    identity: Identity,
    requirements: CheckRequirements,
    plan: CheckPlan,
) -> CompiledCheck:
    return CompiledCheck(
        id=build_check_id(project_name, contract_name, check_type.value),
        name=check_type.value,
        check_type=check_type,
        origin=CheckOrigin(
            kind=CheckOriginKind.CHECK_PACK,
            name=BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        ),
        identity=identity,
        requirements=requirements,
        plan=plan,
    )


def _grain_check_requirements(capability: AdapterCapability) -> CheckRequirements:
    return CheckRequirements(
        requires_grain_keys=True,
        required_capabilities=(capability,),
    )


def _basic_equivalence_requires_grain_diagnostic() -> Diagnostic:
    return Diagnostic(
        code=VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS,
        severity=DiagnosticSeverity.ERROR,
        message=(
            "`recon_core.basic_equivalence` requires `grain.keys` because it "
            "expands into key coverage and key safety checks."
        ),
        resource_type="check_pack",
        resource_name=BASIC_EQUIVALENCE_CHECK_PACK_NAME,
        hint="Add `grain.keys` to the contract or remove the check pack.",
    )


def _unknown_check_pack_diagnostic(check_pack_name: str) -> Diagnostic:
    return Diagnostic(
        code=UNKNOWN_CHECK_PACK,
        severity=DiagnosticSeverity.ERROR,
        message=f"Unknown check pack: {check_pack_name}.",
        resource_type="check_pack",
        resource_name=check_pack_name,
        hint="Use a built-in check pack or install a package that provides this check pack.",
    )
