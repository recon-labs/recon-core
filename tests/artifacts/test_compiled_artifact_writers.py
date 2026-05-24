from pathlib import Path

import pytest
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


def test_compiled_contract_writer_rejects_unexpected_overwrite(tmp_path: Path) -> None:
    artifact = _compiled_contract_artifact()
    writer = CompiledContractWriter()
    writer.write(artifact, tmp_path / "target")

    with pytest.raises(FileExistsError, match="already exists"):
        writer.write(artifact, tmp_path / "target")


def test_compiled_contract_writer_rejects_case_insensitive_collision(tmp_path: Path) -> None:
    writer = CompiledContractWriter()
    writer.write(
        _compiled_contract_artifact(contract_name="Sales"),
        tmp_path / "target",
    )

    with pytest.raises(FileExistsError, match="case-insensitive"):
        writer.write(
            _compiled_contract_artifact(contract_name="sales"),
            tmp_path / "target",
        )


def test_compiled_contract_writer_rejects_path_like_contract_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="safe artifact filename"):
        CompiledContractWriter().write(
            _compiled_contract_artifact(contract_name="../outside"),
            tmp_path / "target",
        )

    assert not (tmp_path / "target" / "outside.yml").exists()


def test_compiled_contract_writer_rejects_symlinked_artifact_directory(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "target"
    external_path = tmp_path / "external"
    external_path.mkdir()
    target_path.mkdir()
    try:
        (target_path / "compiled_contracts").symlink_to(
            external_path,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    with pytest.raises(FileExistsError, match="symlink"):
        CompiledContractWriter().write(_compiled_contract_artifact(), target_path)


def test_compiled_contract_writer_allows_explicit_overwrite(tmp_path: Path) -> None:
    artifact = _compiled_contract_artifact()
    writer = CompiledContractWriter()
    writer.write(artifact, tmp_path / "target")

    output_path = writer.write(artifact, tmp_path / "target", overwrite=True)

    assert yaml.safe_load(output_path.read_text(encoding="utf-8")) == artifact.to_dict()


def test_compiled_contract_writer_rejects_ambiguous_overwrite_regardless_of_directory_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_path = tmp_path / "target"
    output_dir = target_path / "compiled_contracts"
    output_dir.mkdir(parents=True)
    exact_path = output_dir / "sales.yml"
    variant_path = output_dir / "Sales.yml"
    exact_path.write_text("exact\n", encoding="utf-8")
    original_iterdir = Path.iterdir

    def fake_iterdir(path: Path):
        if path == output_dir:
            return iter((exact_path, variant_path))
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    with pytest.raises(FileExistsError, match="case-insensitive"):
        CompiledContractWriter().write(
            _compiled_contract_artifact(contract_name="sales"),
            target_path,
            overwrite=True,
        )


def test_compiled_check_writer_creates_directory_and_writes_yaml(tmp_path: Path) -> None:
    artifact = _compiled_checks_artifact()

    output_path = CompiledCheckWriter().write(artifact, tmp_path / "target")

    assert output_path == tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    assert yaml.safe_load(output_path.read_text(encoding="utf-8")) == artifact.to_dict()
    assert output_path.read_text(encoding="utf-8").endswith("\n")


def test_compiled_check_writer_rejects_unexpected_overwrite(tmp_path: Path) -> None:
    artifact = _compiled_checks_artifact()
    writer = CompiledCheckWriter()
    writer.write(artifact, tmp_path / "target")

    with pytest.raises(FileExistsError, match="already exists"):
        writer.write(artifact, tmp_path / "target")


def test_compiled_check_writer_rejects_case_insensitive_collision(tmp_path: Path) -> None:
    writer = CompiledCheckWriter()
    writer.write(
        _compiled_checks_artifact(contract_name="Sales"),
        tmp_path / "target",
    )

    with pytest.raises(FileExistsError, match="case-insensitive"):
        writer.write(
            _compiled_checks_artifact(contract_name="sales"),
            tmp_path / "target",
        )


def test_compiled_check_writer_rejects_path_like_contract_name(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="safe artifact filename"):
        CompiledCheckWriter().write(
            _compiled_checks_artifact(contract_name="../outside"),
            tmp_path / "target",
        )

    assert not (tmp_path / "target" / "outside.yml").exists()


def test_compiled_check_writer_rejects_symlinked_artifact_directory(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "target"
    external_path = tmp_path / "external"
    external_path.mkdir()
    target_path.mkdir()
    try:
        (target_path / "compiled_checks").symlink_to(
            external_path,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    with pytest.raises(FileExistsError, match="symlink"):
        CompiledCheckWriter().write(_compiled_checks_artifact(), target_path)


def test_compiled_check_writer_allows_explicit_overwrite(tmp_path: Path) -> None:
    artifact = _compiled_checks_artifact()
    writer = CompiledCheckWriter()
    writer.write(artifact, tmp_path / "target")

    output_path = writer.write(artifact, tmp_path / "target", overwrite=True)

    assert yaml.safe_load(output_path.read_text(encoding="utf-8")) == artifact.to_dict()


def _compiled_contract_artifact(
    contract_name: str = "customer_revenue",
) -> CompiledContractArtifact:
    return CompiledContractArtifact(
        artifact_type=CompiledArtifactType.COMPILED_CONTRACT,
        recon_version="0.0.test",
        generated_at="2026-05-23T12:00:00Z",
        invocation_id="01JTESTINVOCATION0000000000",
        project=CompiledProject(name="ecommerce_recon", version="0.1.0"),
        contract=CompiledContractReference(
            id=f"contract.ecommerce_recon.{contract_name}",
            name=contract_name,
            source_file=f"contracts/{contract_name}.yml",
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


def _compiled_checks_artifact(contract_name: str = "customer_revenue") -> CompiledChecksArtifact:
    return CompiledChecksArtifact(
        artifact_type=CompiledArtifactType.COMPILED_CHECKS,
        recon_version="0.0.test",
        generated_at="2026-05-23T12:00:00Z",
        invocation_id="01JTESTINVOCATION0000000000",
        project=CompiledProject(name="ecommerce_recon", version="0.1.0"),
        contract=CompiledContractReference(
            id=f"contract.ecommerce_recon.{contract_name}",
            name=contract_name,
            source_file=f"contracts/{contract_name}.yml",
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
