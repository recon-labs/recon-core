"""Compiled SQL artifact writer."""

from dataclasses import dataclass
from pathlib import Path

from recon_core.adapters.models import RenderedSql
from recon_core.artifacts._paths import (
    ensure_real_artifact_directory,
    ensure_safe_artifact_write,
    reject_symlinked_path_components,
)

COMPILED_SQL_DIR_NAME = "compiled_sql"


@dataclass(frozen=True, slots=True)
class CompiledSqlWriteRequest:
    """One compiled-check SQL output request."""

    contract_name: str
    check_id: str
    rendered_sql: tuple[RenderedSql, ...]


@dataclass(frozen=True, slots=True)
class CompiledSqlWriteResult:
    """SQL paths written for one compiled-check SQL output request."""

    contract_name: str
    check_id: str
    sql_paths: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CompiledSqlWritePlan:
    request: CompiledSqlWriteRequest
    check_dir: Path
    output_paths: tuple[Path, ...]
    sql_paths: tuple[str, ...]


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
        results = self.write_batch(
            requests=(
                CompiledSqlWriteRequest(
                    contract_name=contract_name,
                    check_id=check_id,
                    rendered_sql=rendered_sql,
                ),
            ),
            target_path=target_path,
            overwrite=overwrite,
        )
        return results[0].sql_paths

    def write_batch(
        self,
        *,
        requests: tuple[CompiledSqlWriteRequest, ...],
        target_path: Path,
        overwrite: bool = False,
    ) -> tuple[CompiledSqlWriteResult, ...]:
        """Write a batch of compiled SQL artifacts after preflighting all outputs."""
        plans = _compiled_sql_write_plans(requests, target_path=target_path)
        _validate_compiled_sql_write_plans(plans)
        if not plans:
            return ()

        output_root = target_path / COMPILED_SQL_DIR_NAME
        _preflight_compiled_sql_directories(plans, output_root)
        for plan in plans:
            _preflight_compiled_sql_output_paths(plan.output_paths, overwrite=overwrite)

        ensure_real_artifact_directory(output_root)

        for plan in plans:
            contract_dir = _ensure_safe_nested_directory(output_root, plan.request.contract_name)
            _ensure_safe_nested_directory(contract_dir, plan.request.check_id)

        results: list[CompiledSqlWriteResult] = []
        for plan in plans:
            for rendered, output_path in zip(
                plan.request.rendered_sql,
                plan.output_paths,
                strict=True,
            ):
                output_path.write_text(_sql_text(rendered.sql), encoding="utf-8")
            results.append(
                CompiledSqlWriteResult(
                    contract_name=plan.request.contract_name,
                    check_id=plan.request.check_id,
                    sql_paths=plan.sql_paths,
                )
            )

        return tuple(results)


def _compiled_sql_write_plans(
    requests: tuple[CompiledSqlWriteRequest, ...],
    *,
    target_path: Path,
) -> tuple[_CompiledSqlWritePlan, ...]:
    plans: list[_CompiledSqlWritePlan] = []
    output_root = target_path / COMPILED_SQL_DIR_NAME

    for request in requests:
        check_dir = output_root / request.contract_name / request.check_id
        output_paths = tuple(
            check_dir / f"{rendered.step_name}.sql" for rendered in request.rendered_sql
        )
        plans.append(
            _CompiledSqlWritePlan(
                request=request,
                check_dir=check_dir,
                output_paths=output_paths,
                sql_paths=tuple(
                    output_path.relative_to(target_path).as_posix() for output_path in output_paths
                ),
            )
        )

    return tuple(plans)


def _validate_compiled_sql_write_plans(plans: tuple[_CompiledSqlWritePlan, ...]) -> None:
    seen_output_paths: dict[str, str] = {}
    seen_check_dirs: dict[str, str] = {}

    for plan in plans:
        _validate_compiled_sql_batch(
            contract_name=plan.request.contract_name,
            check_id=plan.request.check_id,
            rendered_sql=plan.request.rendered_sql,
        )

        check_dir_key = plan.check_dir.as_posix().casefold()
        check_dir_display = plan.check_dir.as_posix()
        existing_check_dir = seen_check_dirs.get(check_dir_key)
        if existing_check_dir is not None:
            if existing_check_dir == check_dir_display:
                raise ValueError(f"Compiled SQL check path {check_dir_display} is not unique.")
            raise FileExistsError(
                f"Compiled SQL check path {check_dir_display} has a case-insensitive "
                f"collision with planned artifact {existing_check_dir}."
            )
        seen_check_dirs[check_dir_key] = check_dir_display

        for output_path in plan.output_paths:
            output_path_key = output_path.as_posix().casefold()
            output_path_display = output_path.as_posix()
            existing_output_path = seen_output_paths.get(output_path_key)
            if existing_output_path is not None:
                if existing_output_path == output_path_display:
                    raise ValueError(
                        f"Compiled SQL output path {output_path_display} is not unique."
                    )
                raise FileExistsError(
                    f"Compiled SQL output path {output_path_display} has a "
                    "case-insensitive collision with planned artifact "
                    f"{existing_output_path}."
                )
            seen_output_paths[output_path_key] = output_path_display


def _preflight_compiled_sql_directories(
    plans: tuple[_CompiledSqlWritePlan, ...],
    output_root: Path,
) -> None:
    _preflight_real_artifact_directory(output_root)
    for plan in plans:
        contract_dir = _preflight_safe_nested_directory(
            output_root,
            plan.request.contract_name,
        )
        _preflight_safe_nested_directory(contract_dir, plan.request.check_id)


def _preflight_compiled_sql_output_paths(
    output_paths: tuple[Path, ...],
    *,
    overwrite: bool,
) -> None:
    for output_path in output_paths:
        ensure_safe_artifact_write(output_path, overwrite=overwrite)


def _validate_compiled_sql_batch(
    *,
    contract_name: str,
    check_id: str,
    rendered_sql: tuple[RenderedSql, ...],
) -> None:
    _validate_compiled_sql_path_segment(contract_name)
    _validate_compiled_sql_path_segment(check_id)
    if not rendered_sql:
        raise ValueError(f"Compiled SQL for check {check_id!r} must contain at least one SQL step.")

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


def _preflight_real_artifact_directory(output_dir: Path) -> None:
    reject_symlinked_path_components(output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise FileExistsError(f"Compiled SQL output path is not a directory: {output_dir}")


def _preflight_safe_nested_directory(parent: Path, directory_name: str) -> Path:
    _validate_compiled_sql_path_segment(directory_name)
    _preflight_real_artifact_directory(parent)

    output_dir = parent / directory_name
    reject_symlinked_path_components(output_dir)
    if not parent.exists():
        return output_dir

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

    if output_dir.exists() and not output_dir.is_dir():
        raise FileExistsError(f"Compiled SQL output path is not a directory: {output_dir}")
    return output_dir


def _ensure_safe_nested_directory(parent: Path, directory_name: str) -> Path:
    output_dir = _preflight_safe_nested_directory(parent, directory_name)
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
