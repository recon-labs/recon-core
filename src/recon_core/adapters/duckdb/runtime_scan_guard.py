"""DuckDB bounded local/dev runtime scan guard."""

from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from recon_core.adapters.runtime_safety import (
    RuntimeSafetyCheckRequest,
    RuntimeScanSafetyStatus,
)
from recon_core.profiles import ConnectionConfig

_MAX_BOUNDED_LOCAL_DUCKDB_BYTES = 64 * 1024 * 1024
_DUCKDB_LOCAL_SIDECAR_SUFFIXES = (".wal", ".tmp")


@dataclass(frozen=True, slots=True)
class _DuckDbRelationName:
    identifier: str
    schema: str | None = None
    catalog: str | None = None


def is_local_duckdb_context(
    source_connection: ConnectionConfig | None,
    target_connection: ConnectionConfig | None,
) -> bool:
    if source_connection is None or target_connection is None:
        return False
    if source_connection.type != "duckdb" or target_connection.type != "duckdb":
        return False
    return _same_connection_context(source_connection, target_connection)


class DuckDbBoundedLocalScanSafetyCheck:
    """DuckDB implementation of the runtime scan safety-check boundary."""

    def scan_safety_status(
        self,
        request: RuntimeSafetyCheckRequest,
    ) -> RuntimeScanSafetyStatus:
        if request.source_relation is None or request.target_relation is None:
            return RuntimeScanSafetyStatus()
        if not is_local_duckdb_context(request.source_connection, request.target_connection):
            return RuntimeScanSafetyStatus()
        return bounded_local_duckdb_scan_status(
            request.source_connection,
            source_relation=request.source_relation,
            target_relation=request.target_relation,
            project_root=request.project_root,
        )


def bounded_local_duckdb_scan_status(
    connection: ConnectionConfig | None,
    *,
    source_relation: str | None,
    target_relation: str | None,
    project_root: Path,
) -> RuntimeScanSafetyStatus:
    if connection is None:
        return RuntimeScanSafetyStatus()
    database_path = _local_duckdb_database_path(connection, project_root)
    if database_path is None or not _is_bounded_local_file(database_path):
        return RuntimeScanSafetyStatus(local_dev=True, bounded=False)
    return _duckdb_relations_are_local_base_tables(
        database_path,
        source_relation=source_relation,
        target_relation=target_relation,
    )


def _same_connection_context(left: ConnectionConfig, right: ConnectionConfig) -> bool:
    return left.type == right.type and left.config == right.config


def _local_duckdb_database_path(
    connection: ConnectionConfig,
    project_root: Path,
) -> Path | None:
    database = connection.config.get("database")
    if not isinstance(database, str) or not database:
        return None
    if database == ":memory:":
        return None
    candidate = Path(database)
    if not candidate.is_absolute():
        candidate = project_root / candidate
    try:
        resolved_candidate = candidate.resolve()
        resolved_project_root = project_root.resolve()
    except OSError:
        return None
    if not resolved_candidate.is_relative_to(resolved_project_root):
        return None
    return resolved_candidate


def _is_bounded_local_file(path: Path) -> bool:
    try:
        return (
            path.is_file()
            and not _duckdb_local_sidecar_exists(path)
            and path.stat().st_size <= _MAX_BOUNDED_LOCAL_DUCKDB_BYTES
        )
    except OSError:
        return False


def _duckdb_local_sidecar_exists(path: Path) -> bool:
    for sidecar_path in _duckdb_local_sidecar_paths(path):
        try:
            sidecar_path.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        return True
    return False


def _duckdb_local_sidecar_paths(path: Path) -> tuple[Path, ...]:
    return tuple(
        path.with_name(f"{path.name}{suffix}") for suffix in _DUCKDB_LOCAL_SIDECAR_SUFFIXES
    )


def _duckdb_relations_are_local_base_tables(
    database_path: Path,
    *,
    source_relation: str | None,
    target_relation: str | None,
) -> RuntimeScanSafetyStatus:
    source_relation_name = _duckdb_relation_name(source_relation)
    target_relation_name = _duckdb_relation_name(target_relation)
    if source_relation_name is None or target_relation_name is None:
        return RuntimeScanSafetyStatus(local_dev=True, bounded=False)

    try:
        duckdb: Any = import_module("duckdb")
        connection = duckdb.connect(str(database_path), read_only=True)
    except Exception:
        return RuntimeScanSafetyStatus(
            local_dev=True,
            bounded=False,
            metadata_open_failed=True,
        )

    try:
        local_catalog_names = _local_duckdb_catalog_names(connection, database_path)
        if not local_catalog_names:
            return RuntimeScanSafetyStatus(local_dev=True, bounded=False)
        return RuntimeScanSafetyStatus(
            local_dev=True,
            bounded=all(
                _duckdb_relation_is_local_base_table(
                    connection,
                    relation,
                    local_catalog_names=local_catalog_names,
                )
                for relation in (source_relation_name, target_relation_name)
            ),
        )
    except Exception:
        return RuntimeScanSafetyStatus(local_dev=True, bounded=False)
    finally:
        with suppress(Exception):
            connection.close()


def _duckdb_relation_name(
    relation_name: str | None,
) -> _DuckDbRelationName | None:
    parts = _relation_name_parts(relation_name)
    if parts is None:
        return None
    if len(parts) == 1:
        return _DuckDbRelationName(identifier=parts[0])
    if len(parts) == 2:
        return _DuckDbRelationName(schema=parts[0], identifier=parts[1])
    return _DuckDbRelationName(catalog=parts[0], schema=parts[1], identifier=parts[2])


def _relation_name_parts(relation_name: str | None) -> tuple[str, ...] | None:
    if relation_name is None:
        return None
    raw_parts = relation_name.split(".")
    parts = tuple(part for part in raw_parts if part)
    if len(parts) not in {1, 2, 3} or len(parts) != len(raw_parts):
        return None
    return parts


def _local_duckdb_catalog_names(connection: Any, database_path: Path) -> frozenset[str]:
    rows = connection.execute("pragma database_list").fetchall()
    catalog_names: set[str] = set()
    resolved_database_path = database_path.resolve()
    for row in rows:
        if not isinstance(row, tuple) or len(row) < 3:
            continue
        catalog_name = row[1]
        catalog_path = row[2]
        if not isinstance(catalog_name, str) or not isinstance(catalog_path, str):
            continue
        try:
            if Path(catalog_path).resolve() == resolved_database_path:
                catalog_names.add(_duckdb_identifier_key(catalog_name))
        except OSError:
            continue
    return frozenset(catalog_names)


def _duckdb_relation_is_local_base_table(
    connection: Any,
    relation: _DuckDbRelationName,
    *,
    local_catalog_names: frozenset[str],
) -> bool:
    predicates = ["lower(table_name) = lower(?)"]
    parameters: list[str] = [relation.identifier]
    if relation.schema is not None:
        predicates.append("lower(table_schema) = lower(?)")
        parameters.append(relation.schema)
    if relation.catalog is not None:
        predicates.append("lower(table_catalog) = lower(?)")
        parameters.append(relation.catalog)

    rows = connection.execute(
        "select table_catalog, table_schema, table_name, table_type "
        "from information_schema.tables "
        f"where {' and '.join(predicates)}",
        parameters,
    ).fetchall()
    local_rows = tuple(
        row
        for row in rows
        if (
            isinstance(row, tuple)
            and len(row) >= 4
            and isinstance(row[0], str)
            and _duckdb_identifier_key(row[0]) in local_catalog_names
        )
    )
    if len(rows) != 1 or len(local_rows) != 1:
        return False
    table_type = local_rows[0][3]
    return isinstance(table_type, str) and table_type.upper() == "BASE TABLE"


def _duckdb_identifier_key(identifier: str) -> str:
    return identifier.casefold()
