from pathlib import Path

import yaml

from recon_core.artifacts import CompiledCheckWriter, CompiledContractWriter
from recon_core.compiler.models import (
    CheckOrigin,
    CheckOriginKind,
    CheckPlan,
    CheckRequirements,
    CompiledArtifactType,
    CompiledCheck,
    CompiledChecksArtifact,
    CompiledCheckType,
    CompiledContractArtifact,
    CompiledContractReference,
    CompiledEndpoint,
    CompiledProject,
    Identity,
    IdentityKind,
    OperationSide,
    TypedOperation,
)


def test_compiled_contract_writer_creates_directory_and_writes_yaml(tmp_path: Path) -> None:
    artifact = _compiled_contract_artifact()

    output_path = CompiledContractWriter().write(artifact, tmp_path / "target")

    assert output_path == tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    assert yaml.safe_load(output_path.read_text(encoding="utf-8")) == artifact.to_dict()
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_compiled_check_writer_creates_directory_and_writes_yaml(tmp_path: Path) -> None:
    artifact = _compiled_checks_artifact()

    output_path = CompiledCheckWriter().write(artifact, tmp_path / "target")

    assert output_path == tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    assert yaml.safe_load(output_path.read_text(encoding="utf-8")) == artifact.to_dict()
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def _compiled_contract_artifact() -> CompiledContractArtifact:
    return CompiledContractArtifact(
        artifact_type=CompiledArtifactType.COMPILED_CONTRACT,
        recon_version="0.0.test",
        generated_at="2026-05-23T12:00:00Z",
        invocation_id="01JTESTINVOCATION0000000000",
        project=CompiledProject(name="ecommerce_recon", version="0.1.0"),
        contract=CompiledContractReference(
            id="contract.ecommerce_recon.customer_revenue",
            name="customer_revenue",
            source_file="contracts/customer_revenue.yml",
            authored_version=1,
        ),
        source=CompiledEndpoint(
            connection="legacy",
            relation="qa.customer_source",
        ),
        target=CompiledEndpoint(
            connection="warehouse",
            relation="qa.customer_target",
        ),
        grain_keys=("customer_id",),
    )


def _compiled_checks_artifact() -> CompiledChecksArtifact:
    return CompiledChecksArtifact(
        artifact_type=CompiledArtifactType.COMPILED_CHECKS,
        recon_version="0.0.test",
        generated_at="2026-05-23T12:00:00Z",
        invocation_id="01JTESTINVOCATION0000000000",
        project=CompiledProject(name="ecommerce_recon", version="0.1.0"),
        contract=CompiledContractReference(
            id="contract.ecommerce_recon.customer_revenue",
            name="customer_revenue",
            source_file="contracts/customer_revenue.yml",
        ),
        checks=(
            CompiledCheck(
                id="check.ecommerce_recon.customer_revenue.row_count_diff",
                name="row_count_diff",
                check_type=CompiledCheckType.ROW_COUNT_DIFF,
                origin=CheckOrigin(
                    kind=CheckOriginKind.CHECK_PACK,
                    name="recon_core.basic_equivalence",
                ),
                identity=Identity(kind=IdentityKind.NONE),
                requirements=CheckRequirements(),
                plan=CheckPlan(
                    id="plan.ecommerce_recon.customer_revenue.row_count_diff",
                    operations=(TypedOperation.row_count(side=OperationSide.SOURCE),),
                    required_capabilities=(),
                ),
            ),
        ),
    )
