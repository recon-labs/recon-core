"""DuckDB bounded local/dev runtime scan guard."""

from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from stat import S_ISREG
from string import ascii_lowercase, ascii_uppercase
from typing import Any

from recon_core.adapters._project_binding import (
    _LocalFileIdentity,
    _MAX_BOUNDED_LOCAL_DUCKDB_BYTES,
)
from recon_core.adapters.models import Relation
from recon_core.adapters.runtime_safety import (
    RuntimeSafetyCheckRequest,
    RuntimeScanSafetyStatus,
)
from recon_core.profiles import ConnectionConfig

_DUCKDB_LOCAL_SIDECAR_SUFFIXES = (".wal", ".tmp")
_ASCII_IDENTIFIER_TRANSLATION = str.maketrans(ascii_uppercase, ascii_lowercase)


class _BindingMetadataError(ValueError):
    """Malformed native catalog evidence; do not expose catalog contents."""


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
    except (OSError, RuntimeError, ValueError):
        return None
    if not resolved_candidate.is_relative_to(resolved_project_root):
        return None
    return resolved_candidate


def _local_file_identity(
    connection: ConnectionConfig, project_root: Path
) -> _LocalFileIdentity | None:
    path = _local_duckdb_database_path(connection, project_root)
    return _current_file_identity(path) if path is not None else None


def _current_file_identity(path: Path) -> _LocalFileIdentity | None:
    try:
        if path.resolve(strict=True) != path or _duckdb_local_sidecar_exists(path):
            return None
        info = path.stat()
        if not S_ISREG(info.st_mode):
            return None
        return _LocalFileIdentity(path, info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    except (OSError, RuntimeError, ValueError):
        return None


def _is_bounded_local_file(path: Path) -> bool:
    identity = _current_file_identity(path)
    return identity is not None and identity.size <= _MAX_BOUNDED_LOCAL_DUCKDB_BYTES


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
                _resolve_local_base_table(
                    connection,
                    relation,
                    local_catalog_names=local_catalog_names,
                )
                is not None
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
    if not isinstance(rows, list | tuple):
        raise _BindingMetadataError()
    catalog_names: set[str] = set()
    matching_paths = 0
    resolved_database_path = database_path.resolve()
    for row in rows:
        if not isinstance(row, tuple) or len(row) != 3:
            raise _BindingMetadataError()
        index, catalog_name, catalog_path = row
        if type(index) is not int or not isinstance(catalog_name, str) or not catalog_name:
            raise _BindingMetadataError()
        # In-memory/system catalog entries may not have a filesystem path.
        if catalog_path is None or catalog_path == "":
            continue
        if not isinstance(catalog_path, str):
            raise _BindingMetadataError()
        try:
            if Path(catalog_path).resolve() == resolved_database_path:
                matching_paths += 1
                catalog_names.add(_duckdb_identifier_key(catalog_name))
        except (OSError, RuntimeError, ValueError):
            raise _BindingMetadataError() from None
    if matching_paths > 1:
        return frozenset()
    return frozenset(catalog_names)


def _resolve_local_base_table(
    connection: Any,
    relation: _DuckDbRelationName,
    *,
    local_catalog_names: frozenset[str],
) -> Relation | None:
    # DuckDB identifiers are ASCII-case-insensitive, not Unicode-case-insensitive.
    # Use the same normalization in catalog and relation lookups.
    predicates = ["translate(table_name, ?, ?) = ?"]
    parameters = [ascii_uppercase, ascii_lowercase, _duckdb_identifier_key(relation.identifier)]
    if relation.schema is not None:
        predicates.append("translate(table_schema, ?, ?) = ?")
        parameters.extend(
            (ascii_uppercase, ascii_lowercase, _duckdb_identifier_key(relation.schema))
        )
    if relation.catalog is not None:
        predicates.append("translate(table_catalog, ?, ?) = ?")
        parameters.extend(
            (ascii_uppercase, ascii_lowercase, _duckdb_identifier_key(relation.catalog))
        )

    rows = connection.execute(
        "select table_catalog, table_schema, table_name, table_type "
        "from information_schema.tables "
        f"where {' and '.join(predicates)} limit 2",
        parameters,
    ).fetchmany(2)
    if not isinstance(rows, list | tuple) or any(
        not isinstance(row, tuple)
        or len(row) != 4
        or any(not isinstance(value, str) or not value for value in row)
        for row in rows
    ):
        raise _BindingMetadataError()
    if len(rows) != 1:
        return None
    catalog, schema, identifier, table_type = rows[0]
    if _duckdb_identifier_key(catalog) not in local_catalog_names or table_type != "BASE TABLE":
        return None
    return Relation(identifier=identifier, schema=schema, catalog=catalog)


def _duckdb_identifier_key(identifier: str) -> str:
    return identifier.translate(_ASCII_IDENTIFIER_TRANSLATION)
