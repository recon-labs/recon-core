"""Compiled SQL artifact writer."""

from pathlib import Path

from recon_core.adapters.models import RenderedSql
from recon_core.artifacts._paths import (
    ensure_real_artifact_directory,
    ensure_safe_artifact_write,
)

COMPILED_SQL_DIR_NAME = "compiled_sql"


class CompiledSqlWriter:
    """Write rendered SQL artifacts to a target directory."""

    def write(
        self,
        *,
        contract_name: str,
        check_id: str,
        rendered_sql: tuple[RenderedSql, ...],
        target_path: Path,
        overwrite: bool = False,
    ) -> tuple[str, ...]:
        _validate_compiled_sql_batch(
            contract_name=contract_name,
            check_id=check_id,
            rendered_sql=rendered_sql,
        )
        output_root = target_path / COMPILED_SQL_DIR_NAME
        ensure_real_artifact_directory(output_root)
        contract_dir = _ensure_safe_nested_directory(output_root, contract_name)
        check_dir = _ensure_safe_nested_directory(contract_dir, check_id)

        sql_paths: list[str] = []
        output_paths = tuple(check_dir / f"{rendered.step_name}.sql" for rendered in rendered_sql)
        for output_path in output_paths:
            ensure_safe_artifact_write(output_path, overwrite=overwrite)

        for rendered, output_path in zip(rendered_sql, output_paths, strict=True):
            output_path.write_text(_sql_text(rendered.sql), encoding="utf-8")
            sql_paths.append(output_path.relative_to(target_path).as_posix())

        return tuple(sql_paths)


def _validate_compiled_sql_batch(
    *,
    contract_name: str,
    check_id: str,
    rendered_sql: tuple[RenderedSql, ...],
) -> None:
    _validate_compiled_sql_path_segment(contract_name)
    _validate_compiled_sql_path_segment(check_id)

    seen_step_names: set[str] = set()
    for rendered in rendered_sql:
        _validate_compiled_sql_path_segment(rendered.step_name)
        normalized_step_name = rendered.step_name.casefold()
        if normalized_step_name in seen_step_names:
            raise ValueError(
                f"Compiled SQL step name {rendered.step_name!r} is not unique "
                f"for check {check_id!r}."
            )
        seen_step_names.add(normalized_step_name)


def _ensure_safe_nested_directory(parent: Path, directory_name: str) -> Path:
    _validate_compiled_sql_path_segment(directory_name)
    ensure_real_artifact_directory(parent)

    matching_paths = tuple(
        existing_path
        for existing_path in parent.iterdir()
        if existing_path.name.casefold() == directory_name.casefold()
    )
    case_collisions = tuple(path for path in matching_paths if path.name != directory_name)
    if case_collisions:
        colliding_names = ", ".join(path.name for path in case_collisions)
        raise FileExistsError(
            f"Compiled SQL directory {directory_name} has a case-insensitive collision "
            f"with existing artifact {colliding_names} under {parent}."
        )

    output_dir = parent / directory_name
    if output_dir.exists() and not output_dir.is_dir():
        raise FileExistsError(f"Compiled SQL output path is not a directory: {output_dir}")

    ensure_real_artifact_directory(output_dir)
    return output_dir


def _validate_compiled_sql_path_segment(path_segment: str) -> None:
    if (
        not path_segment
        or path_segment in {".", ".."}
        or "/" in path_segment
        or "\\" in path_segment
        or Path(path_segment).is_absolute()
    ):
        raise ValueError(
            f"Compiled SQL path segment {path_segment!r} is not a safe compiled SQL path segment."
        )


def _sql_text(sql: str) -> str:
    return sql if sql.endswith("\n") else f"{sql}\n"
