from pathlib import Path
from typing import Any, cast

import pytest

from recon_core.adapters import RenderedSql
from recon_core.artifacts import (
    COMPILED_SQL_DIR_NAME,
    CompiledSqlWriter,
    CompiledSqlWriteRequest,
)


def test_compiled_sql_writer_creates_nested_sql_artifacts(tmp_path: Path) -> None:
    rendered_sql = (
        RenderedSql(
            sql="select count(*) as row_count\nfrom qa.customer_source",
            operation_type="row_count",
            step_name="00-row_count-source",
            required_capabilities=("row_count",),
        ),
        RenderedSql(
            sql="select count(*) as row_count\nfrom qa.customer_target\n",
            operation_type="row_count",
            step_name="01-row_count-target",
            required_capabilities=("row_count",),
        ),
    )

    sql_paths = CompiledSqlWriter().write(
        contract_name="customer_revenue",
        check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
        rendered_sql=rendered_sql,
        target_path=tmp_path / "target",
    )

    assert sql_paths == (
        "compiled_sql/customer_revenue/"
        "check.ecommerce_recon.customer_revenue.row_count_diff/00-row_count-source.sql",
        "compiled_sql/customer_revenue/"
        "check.ecommerce_recon.customer_revenue.row_count_diff/01-row_count-target.sql",
    )
    assert (
        tmp_path
        / "target"
        / COMPILED_SQL_DIR_NAME
        / "customer_revenue"
        / "check.ecommerce_recon.customer_revenue.row_count_diff"
        / "00-row_count-source.sql"
    ).read_text(encoding="utf-8") == "select count(*) as row_count\nfrom qa.customer_source\n"
    assert (
        tmp_path
        / "target"
        / COMPILED_SQL_DIR_NAME
        / "customer_revenue"
        / "check.ecommerce_recon.customer_revenue.row_count_diff"
        / "01-row_count-target.sql"
    ).read_text(encoding="utf-8") == "select count(*) as row_count\nfrom qa.customer_target\n"


def test_compiled_sql_writer_rejects_path_like_names(tmp_path: Path) -> None:
    writer = CompiledSqlWriter()
    rendered_sql = (
        RenderedSql(
            sql="select 1",
            operation_type="row_count",
            step_name="00-row_count-source",
        ),
    )

    with pytest.raises(ValueError, match="safe compiled SQL path segment"):
        writer.write(
            contract_name="../outside",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=rendered_sql,
            target_path=tmp_path / "target",
        )

    with pytest.raises(ValueError, match="safe compiled SQL path segment"):
        writer.write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon/customer_revenue.row_count_diff",
            rendered_sql=rendered_sql,
            target_path=tmp_path / "target",
        )

    with pytest.raises(ValueError, match="safe compiled SQL path segment"):
        writer.write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=(
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="../outside",
                ),
            ),
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / "outside.sql").exists()


def test_compiled_sql_writer_rejects_invalid_later_step_without_partial_sql(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="safe compiled SQL path segment"):
        CompiledSqlWriter().write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=(
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="00-row_count-source",
                ),
                RenderedSql(
                    sql="select 2",
                    operation_type="row_count",
                    step_name="../outside",
                ),
            ),
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / COMPILED_SQL_DIR_NAME).exists()


def test_compiled_sql_writer_rejects_empty_rendered_sql_without_partial_sql(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="at least one SQL step"):
        CompiledSqlWriter().write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=(),
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / COMPILED_SQL_DIR_NAME).exists()


@pytest.mark.parametrize(
    ("rendered_sql", "match"),
    [
        (
            (RenderedSql(sql="", operation_type="row_count", step_name="step"),),
            "non-empty string SQL",
        ),
        (
            (RenderedSql(sql="   ", operation_type="row_count", step_name="step"),),
            "non-empty string SQL",
        ),
        (
            (RenderedSql(sql="select 1", operation_type="", step_name="step"),),
            "non-empty operation type",
        ),
        (
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="step",
                    required_capabilities=cast(Any, ["row_count"]),
                ),
            ),
            "required capabilities",
        ),
        (cast(Any, ("not-rendered-sql",)), "not a RenderedSql instance"),
    ],
)
def test_compiled_sql_writer_rejects_malformed_rendered_sql_without_partial_sql(
    tmp_path: Path,
    rendered_sql: tuple[RenderedSql, ...],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        CompiledSqlWriter().write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=rendered_sql,
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / COMPILED_SQL_DIR_NAME).exists()


def test_compiled_sql_writer_rejects_empty_later_rendered_sql_without_partial_sql(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="at least one SQL step"):
        CompiledSqlWriter().write_batch(
            requests=(
                CompiledSqlWriteRequest(
                    contract_name="customer_revenue",
                    check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 1",
                            operation_type="row_count",
                            step_name="00-row_count-source",
                        ),
                    ),
                ),
                CompiledSqlWriteRequest(
                    contract_name="customer_revenue",
                    check_id="check.ecommerce_recon.customer_revenue.key_diff",
                    rendered_sql=(),
                ),
            ),
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / COMPILED_SQL_DIR_NAME).exists()


def test_compiled_sql_writer_rejects_malformed_later_rendered_sql_without_partial_sql(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="non-empty string SQL"):
        CompiledSqlWriter().write_batch(
            requests=(
                CompiledSqlWriteRequest(
                    contract_name="customer_revenue",
                    check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 1",
                            operation_type="row_count",
                            step_name="00-row_count-source",
                        ),
                    ),
                ),
                CompiledSqlWriteRequest(
                    contract_name="customer_revenue",
                    check_id="check.ecommerce_recon.customer_revenue.key_diff",
                    rendered_sql=(
                        RenderedSql(
                            sql="   ",
                            operation_type="key_diff",
                            step_name="00-key_diff-source_minus_target",
                        ),
                    ),
                ),
            ),
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / COMPILED_SQL_DIR_NAME).exists()


def test_compiled_sql_writer_rejects_case_insensitive_duplicate_steps_without_partial_sql(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="not unique"):
        CompiledSqlWriter().write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=(
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="Same",
                ),
                RenderedSql(
                    sql="select 2",
                    operation_type="row_count",
                    step_name="same",
                ),
            ),
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / COMPILED_SQL_DIR_NAME).exists()


def test_compiled_sql_writer_rejects_case_insensitive_check_collisions_without_partial_sql(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileExistsError, match="case-insensitive collision"):
        CompiledSqlWriter().write_batch(
            requests=(
                CompiledSqlWriteRequest(
                    contract_name="customer_revenue",
                    check_id="check.ecommerce_recon.customer_revenue.Total",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 1",
                            operation_type="aggregate",
                            step_name="00-aggregate-source",
                        ),
                    ),
                ),
                CompiledSqlWriteRequest(
                    contract_name="customer_revenue",
                    check_id="check.ecommerce_recon.customer_revenue.total",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 2",
                            operation_type="aggregate",
                            step_name="00-aggregate-source",
                        ),
                    ),
                ),
            ),
            target_path=tmp_path / "target",
        )

    assert not (tmp_path / "target" / COMPILED_SQL_DIR_NAME).exists()


def test_compiled_sql_writer_preflights_existing_output_before_creating_batch_dirs(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "target"
    existing_output = (
        target_path / COMPILED_SQL_DIR_NAME / "existing_contract" / "existing_check" / "step.sql"
    )
    existing_output.parent.mkdir(parents=True)
    existing_output.write_text("old\n", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Artifact already exists"):
        CompiledSqlWriter().write_batch(
            requests=(
                CompiledSqlWriteRequest(
                    contract_name="new_contract",
                    check_id="new_check",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 1",
                            operation_type="row_count",
                            step_name="step",
                        ),
                    ),
                ),
                CompiledSqlWriteRequest(
                    contract_name="existing_contract",
                    check_id="existing_check",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 2",
                            operation_type="row_count",
                            step_name="step",
                        ),
                    ),
                ),
            ),
            target_path=target_path,
        )

    assert not (target_path / COMPILED_SQL_DIR_NAME / "new_contract").exists()
    assert existing_output.read_text(encoding="utf-8") == "old\n"


def test_compiled_sql_writer_preflights_existing_directory_collision_before_creating_batch_dirs(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "target"
    existing_contract_dir = target_path / COMPILED_SQL_DIR_NAME / "Existing_Contract"
    existing_contract_dir.mkdir(parents=True)

    with pytest.raises(FileExistsError, match="case-insensitive collision"):
        CompiledSqlWriter().write_batch(
            requests=(
                CompiledSqlWriteRequest(
                    contract_name="new_contract",
                    check_id="new_check",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 1",
                            operation_type="row_count",
                            step_name="step",
                        ),
                    ),
                ),
                CompiledSqlWriteRequest(
                    contract_name="existing_contract",
                    check_id="existing_check",
                    rendered_sql=(
                        RenderedSql(
                            sql="select 2",
                            operation_type="row_count",
                            step_name="step",
                        ),
                    ),
                ),
            ),
            target_path=target_path,
        )

    assert not (target_path / COMPILED_SQL_DIR_NAME / "new_contract").exists()
    assert existing_contract_dir.is_dir()


def test_compiled_sql_writer_rejects_symlinked_compiled_sql_directory(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "target"
    external_path = tmp_path / "external"
    external_path.mkdir()
    target_path.mkdir()
    try:
        (target_path / COMPILED_SQL_DIR_NAME).symlink_to(
            external_path,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    with pytest.raises(FileExistsError, match="symlink"):
        CompiledSqlWriter().write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=(
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="00-row_count-source",
                ),
            ),
            target_path=target_path,
        )


def test_compiled_sql_writer_rejects_exact_output_symlink_with_overwrite(
    tmp_path: Path,
) -> None:
    target_path = tmp_path / "target"
    output_dir = (
        target_path
        / COMPILED_SQL_DIR_NAME
        / "customer_revenue"
        / "check.ecommerce_recon.customer_revenue.row_count_diff"
    )
    external_path = tmp_path / "external.sql"
    output_dir.mkdir(parents=True)
    external_path.write_text("external\n", encoding="utf-8")
    try:
        (output_dir / "00-row_count-source.sql").symlink_to(external_path)
    except OSError:
        pytest.skip("Filesystem does not support file symlinks.")

    with pytest.raises(FileExistsError, match="symlink"):
        CompiledSqlWriter().write(
            contract_name="customer_revenue",
            check_id="check.ecommerce_recon.customer_revenue.row_count_diff",
            rendered_sql=(
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="00-row_count-source",
                ),
            ),
            target_path=target_path,
            overwrite=True,
        )

    assert external_path.read_text(encoding="utf-8") == "external\n"
