"""Check-engine result model primitives."""

from recon_core.check_engine.dispatch import (
    CHECK_NOT_EXECUTABLE,
    MISSING_ENGINE_CAPABILITY,
    UNSUPPORTED_CHECK_TYPE,
    UNSUPPORTED_EXECUTION_PLACEMENT,
    UNSUPPORTED_MATERIALIZATION_POLICY,
    UNSUPPORTED_TYPED_OPERATION,
    CheckDispatcher,
)
from recon_core.check_engine.engine import (
    BLOCKED_BY_PREREQUISITE,
    CHECK_ENGINE_INTERNAL_ERROR,
    CheckEngine,
    CheckExecutionContext,
)
from recon_core.check_engine.execution import (
    ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED,
    ROW_COUNT_RESULT_INVALID,
    execute_row_count_check,
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
    "BLOCKED_BY_PREREQUISITE",
    "ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED",
    "CHECK_NOT_EXECUTABLE",
    "CHECK_ENGINE_INTERNAL_ERROR",
    "CheckEngine",
    "CheckExecutionContext",
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
    "ROW_COUNT_RESULT_INVALID",
    "MISSING_ENGINE_CAPABILITY",
    "UNSUPPORTED_CHECK_TYPE",
    "UNSUPPORTED_EXECUTION_PLACEMENT",
    "UNSUPPORTED_MATERIALIZATION_POLICY",
    "UNSUPPORTED_TYPED_OPERATION",
    "aggregate_check_status",
    "aggregate_contract_status",
    "execute_row_count_check",
]
