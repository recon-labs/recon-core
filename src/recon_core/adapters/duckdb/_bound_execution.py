"""Private owned read-only DuckDB transaction for project-run binding."""

from importlib import import_module
from typing import Any

from recon_core.adapters.duckdb.runtime_scan_guard import (
    _current_file_identity,
    _duckdb_relation_name,
    _local_duckdb_catalog_names,
    _resolve_local_base_table,
    _LocalFileIdentity,
)
from recon_core.adapters.lifecycle import ADAPTER_CLOSE_FAILED, ADAPTER_CONNECTION_FAILED
from recon_core.adapters.models import Relation
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


class _BoundSessionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.diagnostic = _diagnostic(code, message)


def _diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="adapter",
        resource_name="duckdb",
    )


def _proof_error() -> _BoundSessionError:
    return _BoundSessionError(
        "RC_RUNTIME_BINDING_PROOF_FAILED", "Execution binding could not be verified."
    )


class _OwnedDuckDbSession:
    """Single-use session; the caller must close it in a finally block."""

    def __init__(self, identity: _LocalFileIdentity) -> None:
        self._identity = identity
        self._connection: Any = None
        self._attempted = False
        self._transaction = False
        self._released = True
        self._cleanup: tuple[Diagnostic, ...] | None = None

    @property
    def released(self) -> bool:
        return self._released

    def _verify_file(self) -> None:
        if _current_file_identity(self._identity.path) != self._identity:
            raise _proof_error()

    def open(self) -> None:
        if self._attempted or self._cleanup is not None:
            raise _proof_error()
        self._attempted = True
        self._verify_file()
        try:
            duckdb = import_module("duckdb")
            self._connection = duckdb.connect(str(self._identity.path), read_only=True)
            self._released = False
        except Exception:
            raise _BoundSessionError(
                ADAPTER_CONNECTION_FAILED,
                "Read-only execution session could not be opened or initialized.",
            ) from None
        self._verify_file()
        try:
            self._connection.execute("BEGIN TRANSACTION")
            self._transaction = True
        except Exception:
            raise _BoundSessionError(
                ADAPTER_CONNECTION_FAILED,
                "Read-only execution session could not be opened or initialized.",
            ) from None

    def resolve_relation(self, name: str) -> Relation | None:
        if not self._transaction or self._cleanup is not None:
            raise _proof_error()
        self._verify_file()
        relation = _duckdb_relation_name(name)
        if relation is None:
            return None
        try:
            catalogs = _local_duckdb_catalog_names(self._connection, self._identity.path)
            self._verify_file()
            if not catalogs:
                return None
            return _resolve_local_base_table(
                self._connection, relation, local_catalog_names=catalogs
            )
        except Exception:
            raise _proof_error() from None

    def close(self) -> tuple[Diagnostic, ...]:
        if self._cleanup is not None:
            return self._cleanup
        diagnostics: list[Diagnostic] = []
        if self._connection is not None:
            try:
                if self._transaction:
                    try:
                        self._connection.execute("ROLLBACK")
                    except Exception:
                        diagnostics.append(
                            _diagnostic(ADAPTER_CLOSE_FAILED, "Read-only transaction cleanup failed.")
                        )
            finally:
                self._transaction = False
                try:
                    self._connection.close()
                except Exception:
                    diagnostics.append(
                        _diagnostic(ADAPTER_CLOSE_FAILED, "Read-only execution session cleanup failed.")
                    )
                else:
                    self._released = True
                    self._connection = None
                finally:
                    self._cleanup = tuple(diagnostics)
        else:
            self._cleanup = ()
        return self._cleanup
