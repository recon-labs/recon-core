"""Check-engine result model primitives."""

from recon_core.check_engine.dispatch import (
    CHECK_NOT_EXECUTABLE,
    UNSUPPORTED_CHECK_TYPE,
    UNSUPPORTED_EXECUTION_PLACEMENT,
    UNSUPPORTED_MATERIALIZATION_POLICY,
    UNSUPPORTED_TYPED_OPERATION,
    CheckDispatcher,
)
from recon_core.check_engine.models import (
    CheckReason,
    CheckResult,
    CheckResultDict,
    CheckStatus,
    ContractResult,
    ContractResultDict,
    RunResult,
    RunResultDict,
    RunStatus,
    aggregate_check_status,
    aggregate_contract_status,
)

__all__ = [
    "CHECK_NOT_EXECUTABLE",
    "CheckReason",
    "CheckDispatcher",
    "CheckResult",
    "CheckResultDict",
    "CheckStatus",
    "ContractResult",
    "ContractResultDict",
    "RunResult",
    "RunResultDict",
    "RunStatus",
    "UNSUPPORTED_CHECK_TYPE",
    "UNSUPPORTED_EXECUTION_PLACEMENT",
    "UNSUPPORTED_MATERIALIZATION_POLICY",
    "UNSUPPORTED_TYPED_OPERATION",
    "aggregate_check_status",
    "aggregate_contract_status",
]
