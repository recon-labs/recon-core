"""Compile parsed contracts into compiled artifacts."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from recon_core._version import get_version
from recon_core.compiler.check_packs import expand_check_pack
from recon_core.compiler.ids import (
    build_contract_id,
    invalid_stable_id_part_diagnostic,
    is_valid_stable_id_part,
)
from recon_core.compiler.metrics import compile_metrics
from recon_core.compiler.models import (
    CompiledArtifactType,
    CompiledCheck,
    CompiledChecksArtifact,
    CompiledContractArtifact,
    CompiledContractPolicies,
    CompiledContractReference,
    CompiledEndpoint,
    CompiledProject,
    ResolvedSampling,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.parser import DUPLICATE_CONTRACT, AuthoredContract, AuthoredEndpoint

INVALID_CHECK_PACK_USE = "RC_VALIDATE_INVALID_CHECK_PACK_USE"
INVALID_GRAIN_KEYS = "RC_VALIDATE_INVALID_GRAIN_KEYS"
INVALID_SAMPLING = "RC_VALIDATE_INVALID_SAMPLING"
COMPILED_ARTIFACT_FILENAME_COLLISION = "RC_VALIDATE_COMPILED_ARTIFACT_FILENAME_COLLISION"
UNSUPPORTED_CHECK_PACK_CONFIG = "RC_COMPILE_UNSUPPORTED_CHECK_PACK_CONFIG"
UNSUPPORTED_EXPLICIT_CHECKS = "RC_COMPILE_UNSUPPORTED_EXPLICIT_CHECKS"
DUPLICATE_COMPILED_CHECK = "RC_COMPILE_DUPLICATE_COMPILED_CHECK"


@dataclass(frozen=True, slots=True)
class ContractCompilationArtifacts:
    """Compiled artifacts for one authored contract."""

    contract_artifact: CompiledContractArtifact
    checks_artifact: CompiledChecksArtifact


@dataclass(frozen=True, slots=True)
class ProjectCompilationResult:
    """Result of compiling parsed project contracts."""

    contracts: tuple[ContractCompilationArtifacts, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    invocation_id: str = ""

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )


def compile_project(
    *,
    project_name: str,
    project_version: str | None,
    contracts: Sequence[AuthoredContract],
    invocation_id: str | None = None,
    generated_at: str | None = None,
    recon_version: str | None = None,
) -> ProjectCompilationResult:
    """Compile parsed contracts into contract and check artifacts."""
    resolved_invocation_id = uuid4().hex if invocation_id is None else invocation_id
    resolved_generated_at = _current_timestamp() if generated_at is None else generated_at
    resolved_recon_version = get_version() if recon_version is None else recon_version

    compiled_contracts: list[ContractCompilationArtifacts] = []
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(_stable_project_id_diagnostics(project_name, contracts))
    diagnostics.extend(_duplicate_contract_name_diagnostics(contracts))
    diagnostics.extend(_compiled_artifact_filename_collision_diagnostics(contracts))
    if diagnostics:
        return ProjectCompilationResult(
            diagnostics=tuple(diagnostics),
            invocation_id=resolved_invocation_id,
        )

    for contract in contracts:
        compiled = _compile_contract(
            project_name=project_name,
            project_version=project_version,
            contract=contract,
            invocation_id=resolved_invocation_id,
            generated_at=resolved_generated_at,
            recon_version=resolved_recon_version,
        )
        compiled_contracts.append(compiled)
        diagnostics.extend(compiled.checks_artifact.diagnostics)

    return ProjectCompilationResult(
        contracts=tuple(compiled_contracts),
        diagnostics=tuple(diagnostics),
        invocation_id=resolved_invocation_id,
    )


def _compile_contract(
    *,
    project_name: str,
    project_version: str | None,
    contract: AuthoredContract,
    invocation_id: str,
    generated_at: str,
    recon_version: str,
) -> ContractCompilationArtifacts:
    diagnostics: list[Diagnostic] = []
    grain_keys = _grain_keys(contract, diagnostics)
    sampling = _resolved_sampling(contract, diagnostics)
    checks: list[CompiledCheck] = []

    check_pack_names = _check_pack_names(contract, diagnostics)
    for check_pack_name in check_pack_names:
        expansion = expand_check_pack(
            check_pack_name,
            project_name=project_name,
            contract_name=contract.name,
            grain_keys=grain_keys,
        )
        diagnostics.extend(expansion.diagnostics)
        checks.extend(replace(check, sampling=sampling) for check in expansion.checks)

    metric_compilation = compile_metrics(
        contract.metrics,
        project_name=project_name,
        contract_name=contract.name,
    )
    diagnostics.extend(metric_compilation.diagnostics)
    checks.extend(replace(check, sampling=sampling) for check in metric_compilation.checks)
    checks = _deduplicate_checks(checks, diagnostics)

    contract_id = build_contract_id(project_name, contract.name)
    project = CompiledProject(name=project_name, version=project_version)
    contract_artifact_ref = CompiledContractReference(
        id=contract_id,
        name=contract.name,
        source_file=contract.source_location.path,
        authored_version=contract.version,
    )
    checks_artifact_ref = CompiledContractReference(
        id=contract_id,
        name=contract.name,
        source_file=contract.source_location.path,
    )
    contract_diagnostics = tuple(diagnostics)

    return ContractCompilationArtifacts(
        contract_artifact=CompiledContractArtifact(
            artifact_type=CompiledArtifactType.COMPILED_CONTRACT,
            recon_version=recon_version,
            generated_at=generated_at,
            invocation_id=invocation_id,
            project=project,
            contract=contract_artifact_ref,
            source=_compiled_endpoint(contract.source),
            target=_compiled_endpoint(contract.target),
            grain_keys=grain_keys,
            columns=contract.columns,
            metrics=contract.metrics,
            policies=CompiledContractPolicies(
                sampling=contract.sampling,
                tolerance_policy=contract.tolerance_policy,
                schema=contract.schema,
                cdc=contract.cdc,
                evidence=contract.evidence,
            ),
            diagnostics=contract_diagnostics,
        ),
        checks_artifact=CompiledChecksArtifact(
            artifact_type=CompiledArtifactType.COMPILED_CHECKS,
            recon_version=recon_version,
            generated_at=generated_at,
            invocation_id=invocation_id,
            project=project,
            contract=checks_artifact_ref,
            checks=tuple(checks) if not diagnostics else (),
            diagnostics=contract_diagnostics,
        ),
    )


def _stable_project_id_diagnostics(
    project_name: str,
    contracts: Sequence[AuthoredContract],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    if not is_valid_stable_id_part(project_name):
        diagnostics.append(
            invalid_stable_id_part_diagnostic(
                resource_type="project",
                resource_name=project_name,
                value=project_name,
            )
        )

    for contract in contracts:
        if not is_valid_stable_id_part(contract.name):
            diagnostics.append(
                invalid_stable_id_part_diagnostic(
                    resource_type="contract",
                    resource_name=contract.name,
                    value=contract.name,
                    path=contract.source_location.path,
                )
            )

    return tuple(diagnostics)


def _duplicate_contract_name_diagnostics(
    contracts: Sequence[AuthoredContract],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_contracts: dict[str, AuthoredContract] = {}

    for contract in contracts:
        existing_contract = seen_contracts.get(contract.name)
        if existing_contract is not None:
            diagnostics.append(
                Diagnostic(
                    code=DUPLICATE_CONTRACT,
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Contract name {contract.name} is defined more than once.",
                    resource_type="contract",
                    resource_name=contract.name,
                    path=contract.source_location.path,
                    hint=f"First definition was found at {existing_contract.source_location.path}.",
                )
            )
            continue
        seen_contracts[contract.name] = contract

    return tuple(diagnostics)


def _compiled_artifact_filename_collision_diagnostics(
    contracts: Sequence[AuthoredContract],
) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    seen_contracts_by_filename: dict[str, AuthoredContract] = {}

    for contract in contracts:
        filename = _compiled_contract_filename(contract.name)
        filename_key = filename.casefold()
        existing_contract = seen_contracts_by_filename.get(filename_key)
        if existing_contract is not None and existing_contract.name != contract.name:
            existing_filename = _compiled_contract_filename(existing_contract.name)
            diagnostics.append(
                Diagnostic(
                    code=COMPILED_ARTIFACT_FILENAME_COLLISION,
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        f"Contract names {existing_contract.name} and {contract.name} would "
                        "write case-colliding compiled artifact filenames "
                        f"{existing_filename} and {filename}."
                    ),
                    resource_type="contract",
                    resource_name=contract.name,
                    path=contract.source_location.path,
                    hint=("Use contract names that are unique when compared case-insensitively."),
                )
            )
            continue
        seen_contracts_by_filename[filename_key] = contract

    return tuple(diagnostics)


def _compiled_contract_filename(contract_name: str) -> str:
    return f"{contract_name}.yml"


def _grain_keys(contract: AuthoredContract, diagnostics: list[Diagnostic]) -> tuple[str, ...]:
    if contract.grain is None:
        return ()

    keys = contract.grain.get("keys")
    if not isinstance(keys, list | tuple) or not all(isinstance(key, str) and key for key in keys):
        diagnostics.append(
            Diagnostic(
                code=INVALID_GRAIN_KEYS,
                severity=DiagnosticSeverity.ERROR,
                message="Contract `grain.keys` must be a list of non-empty strings.",
                resource_type="contract",
                resource_name=contract.name,
                path=contract.source_location.path,
                hint="Use `grain: {keys: [...]}` or a YAML list under `grain.keys`.",
            )
        )
        return ()

    return tuple(keys)


def _check_pack_names(
    contract: AuthoredContract,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    checks = contract.checks
    if isinstance(checks, Mapping):
        names = _check_pack_use_names(contract, checks.get("use"), diagnostics)
        unsupported_fields = sorted(set(checks) - {"use"})
        if unsupported_fields:
            diagnostics.append(
                _unsupported_checks_diagnostic(
                    contract,
                    f"Unsupported `checks` fields: {', '.join(unsupported_fields)}.",
                )
            )
        return names

    if isinstance(checks, list | tuple):
        diagnostics.append(
            _unsupported_checks_diagnostic(
                contract,
                "Explicit authored checks are not implemented in the current compiler.",
            )
        )
        return ()

    diagnostics.append(
        _unsupported_checks_diagnostic(
            contract,
            "Contract `checks` must be a mapping with `use` for current compile support.",
        )
    )
    return ()


def _check_pack_use_names(
    contract: AuthoredContract,
    raw_use: object,
    diagnostics: list[Diagnostic],
) -> tuple[str, ...]:
    if raw_use is None:
        return ()
    if not isinstance(raw_use, Sequence) or isinstance(raw_use, str):
        diagnostics.append(_invalid_check_pack_use_diagnostic(contract))
        return ()

    names: list[str] = []
    for item in raw_use:
        if isinstance(item, str) and item:
            names.append(item)
            continue
        if isinstance(item, Mapping):
            name = item.get("name")
            if isinstance(name, str) and name:
                unsupported_fields = sorted(str(field) for field in item if field != "name")
                if unsupported_fields:
                    diagnostics.append(
                        _unsupported_check_pack_config_diagnostic(
                            contract,
                            name,
                            unsupported_fields,
                        )
                    )
                    continue
                names.append(name)
                continue
        diagnostics.append(_invalid_check_pack_use_diagnostic(contract))

    return tuple(names)


def _deduplicate_checks(
    checks: Sequence[CompiledCheck],
    diagnostics: list[Diagnostic],
) -> list[CompiledCheck]:
    deduplicated: list[CompiledCheck] = []
    seen_names: set[str] = set()
    for check in checks:
        if check.name in seen_names:
            diagnostics.append(
                Diagnostic(
                    code=DUPLICATE_COMPILED_CHECK,
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Compiled check name {check.name} is generated more than once.",
                    resource_type="check",
                    resource_name=check.name,
                    hint="Rename explicit metrics or checks so compiled check names are unique.",
                )
            )
            continue
        seen_names.add(check.name)
        deduplicated.append(check)
    return deduplicated


def _resolved_sampling(
    contract: AuthoredContract,
    diagnostics: list[Diagnostic],
) -> ResolvedSampling:
    if contract.sampling is None:
        return ResolvedSampling()

    unsupported_fields = sorted(set(contract.sampling) - {"default_policy"})
    if unsupported_fields:
        diagnostics.append(
            _invalid_sampling_diagnostic(
                contract,
                f"Unsupported `sampling` fields: {', '.join(unsupported_fields)}.",
            )
        )
        return ResolvedSampling()

    default_policy = contract.sampling.get("default_policy")
    if default_policy is None or default_policy == "full":
        return ResolvedSampling()
    if not isinstance(default_policy, str):
        diagnostics.append(
            _invalid_sampling_diagnostic(
                contract,
                "Contract `sampling.default_policy` must be a string.",
            )
        )
        return ResolvedSampling()
    return ResolvedSampling(mode=None, policy=default_policy)


def _compiled_endpoint(endpoint: AuthoredEndpoint) -> CompiledEndpoint:
    return CompiledEndpoint(
        connection=endpoint.connection,
        relation=endpoint.relation,
        query=endpoint.query,
    )


def _invalid_check_pack_use_diagnostic(contract: AuthoredContract) -> Diagnostic:
    return Diagnostic(
        code=INVALID_CHECK_PACK_USE,
        severity=DiagnosticSeverity.ERROR,
        message="Contract `checks.use` must be a list of check-pack names.",
        resource_type="contract",
        resource_name=contract.name,
        path=contract.source_location.path,
        hint="Use `checks: {use: [recon_core.basic_equivalence]}`.",
    )


def _unsupported_check_pack_config_diagnostic(
    contract: AuthoredContract,
    check_pack_name: str,
    unsupported_fields: Sequence[str],
) -> Diagnostic:
    return Diagnostic(
        code=UNSUPPORTED_CHECK_PACK_CONFIG,
        severity=DiagnosticSeverity.ERROR,
        message=(
            f"Check-pack invocation for {check_pack_name} has unsupported fields: "
            f"{', '.join(unsupported_fields)}."
        ),
        resource_type="check_pack",
        resource_name=check_pack_name,
        path=contract.source_location.path,
        hint=(
            "Only `name` is supported in `checks.use` mappings for the current compiler milestone."
        ),
    )


def _unsupported_checks_diagnostic(contract: AuthoredContract, message: str) -> Diagnostic:
    return Diagnostic(
        code=UNSUPPORTED_EXPLICIT_CHECKS,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="contract",
        resource_name=contract.name,
        path=contract.source_location.path,
        hint="Use supported check packs and explicit metrics for this compiler milestone.",
    )


def _invalid_sampling_diagnostic(contract: AuthoredContract, message: str) -> Diagnostic:
    return Diagnostic(
        code=INVALID_SAMPLING,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="contract",
        resource_name=contract.name,
        path=contract.source_location.path,
        hint="Use `sampling: {default_policy: full}` or a named sampling policy.",
    )


def _current_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
