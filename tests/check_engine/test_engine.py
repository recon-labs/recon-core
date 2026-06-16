from pathlib import Path

import pytest

from recon_core.adapters import (
    ADAPTER_API_VERSION,
    AdapterCapabilities,
    BaseAdapter,
    CapabilitySupport,
    ColumnMetadata,
    ConnectionConfig,
    QueryResult,
    Relation,
)
from recon_core.artifacts import (
    LoadedCheckPlan,
    LoadedCompiledCheck,
    LoadedCompiledChecksArtifact,
    LoadedCompiledContractArtifact,
    LoadedCompiledEndpoint,
)
from recon_core.check_engine import (
    BLOCKED_BY_PREREQUISITE,
    CHECK_ENGINE_INTERNAL_ERROR,
    CheckEngine,
    CheckExecutionContext,
    CheckReason,
    CheckResult,
    CheckStatus,
    RunStatus,
)
from recon_core.check_engine.scan_budget import (
    ScanBudgetContext,
    ScanBudgetDecision,
    ScanEstimateState,
    ScanExecutionEnvironment,
    classify_scan_budget,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


def test_engine_assembles_run_and_contract_results_without_execution(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path, checks=(_check(),))

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    assert result.project_name == "ecommerce_recon"
    assert result.status is RunStatus.NOT_EXECUTABLE
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert result.diagnostics == ()
    assert len(result.contract_results) == 1

    contract = result.contract_results[0]
    assert contract.contract_name == "customer_revenue"
    assert contract.status is RunStatus.NOT_EXECUTABLE
    assert len(contract.check_results) == 1

    check = contract.check_results[0]
    assert check.status is CheckStatus.NOT_EXECUTABLE
    assert not check.executed
    assert check.reason_code is CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE
    assert check.source_value is None
    assert check.target_value is None
    assert check.artifact_refs == ()
    assert check.sink_refs == ()


def test_engine_executes_row_count_when_execution_context_is_present(tmp_path: Path) -> None:
    check = _check(
        operations=_row_count_operations(),
        required_capabilities=("row_count",),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((8, 8, 0),),
            row_count=1,
        )
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
        ),
    )

    assert result.status is RunStatus.PASS
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert result.diagnostics == ()

    contract_result = result.contract_results[0]
    assert contract_result.status is RunStatus.PASS

    check_result = contract_result.check_results[0]
    assert check_result.status is CheckStatus.PASS
    assert check_result.executed
    assert check_result.reason_code is None
    assert check_result.source_value == 8
    assert check_result.target_value == 8
    assert check_result.diff_value == 0
    assert check_result.artifact_refs == ()
    assert check_result.sink_refs == ()
    assert check_result.diagnostics == ()
    assert len(adapter.queries) == 1


def test_engine_executes_row_count_when_connection_aliases_share_context(
    tmp_path: Path,
) -> None:
    check = _check(
        operations=_row_count_operations(),
        required_capabilities=("row_count",),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(
        tmp_path,
        source_connection="warehouse",
        target_connection="replica",
    )
    source_connection = ConnectionConfig(
        name="warehouse",
        type="duckdb",
        config={"database": "warehouse.duckdb"},
    )
    target_connection = ConnectionConfig(
        name="replica",
        type="duckdb",
        config={"database": "warehouse.duckdb"},
    )
    adapter = _RecordingDuckDbAdapter(
        connection=source_connection,
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((8, 8, 0),),
            row_count=1,
        ),
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            connections_by_name={
                source_connection.name: source_connection,
                target_connection.name: target_connection,
            },
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert result.status is RunStatus.PASS
    assert check_result.status is CheckStatus.PASS
    assert check_result.executed
    assert len(adapter.queries) == 1


def test_engine_mixes_executable_row_count_and_key_safety_checks(tmp_path: Path) -> None:
    row_count = _check(
        operations=_row_count_operations(),
        required_capabilities=("row_count",),
    )
    missing_keys = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(_key_diff_operation("source_minus_target"),),
        required_capabilities=("key_diff", "cte_support"),
    )
    artifact = _artifact(tmp_path, checks=(row_count, missing_keys))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        results=(
            QueryResult(
                columns=("source_row_count", "target_row_count", "row_count_diff"),
                rows=((4, 4, 0),),
                row_count=1,
            ),
            QueryResult(columns=("failure_count",), rows=((0,),), row_count=1),
        )
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            scan_budget_decisions_by_check_id={
                missing_keys.id: _allowed_scan_budget(),
            },
        ),
    )

    row_count_result, missing_keys_result = result.contract_results[0].check_results
    assert result.status is RunStatus.PASS
    assert row_count_result.status is CheckStatus.PASS
    assert row_count_result.executed
    assert missing_keys_result.status is CheckStatus.PASS
    assert missing_keys_result.executed
    assert missing_keys_result.reason_code is None
    assert missing_keys_result.failure_count == 0
    assert len(adapter.queries) == 2


@pytest.mark.parametrize("rendering_status", ["blocked", "failed"])
def test_engine_blocks_render_blocked_key_safety_checks_before_adapter_query(
    tmp_path: Path,
    rendering_status: str,
) -> None:
    render_block_diagnostic = Diagnostic(
        code="RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS",
        severity=DiagnosticSeverity.ERROR,
        message="SQL rendering was blocked before adapter rendering could start.",
    )
    check = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(_key_diff_operation("source_minus_target"),),
        rendering_status=rendering_status,
        diagnostics=(render_block_diagnostic,),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        result=QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            scan_budget_decisions_by_check_id={check.id: _allowed_scan_budget()},
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert result.status is RunStatus.ERROR
    assert check_result.status is CheckStatus.ERROR
    assert not check_result.executed
    assert check_result.reason_code is None
    assert [diagnostic.code for diagnostic in check_result.diagnostics] == [
        "RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS",
    ]
    assert adapter.queries == []


def test_engine_keeps_unsupported_render_blocked_key_safety_shape_not_executable(
    tmp_path: Path,
) -> None:
    check = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(_key_diff_operation("target_minus_source"),),
        rendering_status="failed",
        diagnostics=(
            Diagnostic(
                code="RC_ADAPTER_OPERATION_RENDER_FAILED",
                severity=DiagnosticSeverity.ERROR,
                message="Rendering failed before runtime.",
            ),
        ),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        result=QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            scan_budget_decisions_by_check_id={check.id: _allowed_scan_budget()},
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert result.status is RunStatus.NOT_EXECUTABLE
    assert check_result.status is CheckStatus.NOT_EXECUTABLE
    assert not check_result.executed
    assert check_result.reason_code is CheckReason.UNSUPPORTED_TYPED_OPERATION
    assert adapter.queries == []


def test_engine_blocks_dependent_check_when_row_count_prerequisite_fails(
    tmp_path: Path,
) -> None:
    row_count = _check(
        operations=_row_count_operations(),
        required_capabilities=("row_count",),
    )
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=(row_count.id,),
    )
    artifact = _artifact(tmp_path, checks=(dependent, row_count))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((7, 9, -2),),
            row_count=1,
        )
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
        ),
    )

    dependent_result, row_count_result = result.contract_results[0].check_results
    assert result.status is RunStatus.FAIL
    assert row_count_result.status is CheckStatus.FAIL
    assert row_count_result.executed
    assert row_count_result.source_value == 7
    assert row_count_result.target_value == 9
    assert row_count_result.diff_value == -2
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.reason_code is CheckReason.PREREQUISITE_FAILED
    assert dependent_result.blocked_by == (row_count.id,)
    assert len(adapter.queries) == 1


def test_engine_blocks_dependent_check_when_key_safety_prerequisite_fails(
    tmp_path: Path,
) -> None:
    duplicate_source_keys = _check(
        check_id="check.ecommerce_recon.customer_revenue.duplicate_source_keys",
        name="duplicate_source_keys",
        check_type="duplicate_source_keys",
        operations=(_duplicate_key_operation("source"),),
        required_capabilities=("duplicate_key",),
    )
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=(duplicate_source_keys.id,),
    )
    artifact = _artifact(tmp_path, checks=(dependent, duplicate_source_keys))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        result=QueryResult(columns=("failure_count",), rows=((1,),), row_count=1)
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            scan_budget_decisions_by_check_id={
                duplicate_source_keys.id: _allowed_scan_budget(),
            },
        ),
    )

    dependent_result, prerequisite_result = result.contract_results[0].check_results
    assert result.status is RunStatus.FAIL
    assert prerequisite_result.status is CheckStatus.FAIL
    assert prerequisite_result.executed
    assert prerequisite_result.failure_count == 1
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.reason_code is CheckReason.PREREQUISITE_FAILED
    assert dependent_result.blocked_by == (duplicate_source_keys.id,)
    assert len(adapter.queries) == 1


def test_engine_preserves_row_count_hard_blockers_before_adapter_execution(
    tmp_path: Path,
) -> None:
    check = _check(
        operations=(
            {
                "type": "row_count",
                "side": "source",
                "execution_placement": "source",
            },
            {"type": "row_count", "side": "target"},
            {"type": "compare_counts"},
        ),
        required_capabilities=("row_count",),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter()

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert check_result.status is CheckStatus.NOT_EXECUTABLE
    assert not check_result.executed
    assert check_result.reason_code is CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT
    assert check_result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT"
    assert adapter.queries == []


@pytest.mark.parametrize(
    ("operations", "expected_reason"),
    [
        (
            (
                {
                    "type": "key_diff",
                    "direction": "source_minus_target",
                    "identity": {"kind": "grain", "keys": ["customer_id"]},
                    "execution_placement": "source",
                },
            ),
            CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        ),
        (
            (
                {
                    "type": "key_diff",
                    "direction": "source_minus_target",
                    "identity": {"kind": "grain", "keys": ["customer_id"]},
                    "materialization_policy": "staging_table",
                },
            ),
            CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY,
        ),
        (
            ({"type": "key_diff", "direction": "source_minus_target"},),
            CheckReason.UNSUPPORTED_TYPED_OPERATION,
        ),
    ],
)
def test_engine_preserves_key_safety_hard_blockers_before_adapter_execution(
    tmp_path: Path,
    operations: tuple[dict[str, object], ...],
    expected_reason: CheckReason,
) -> None:
    check = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=operations,
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        result=QueryResult(columns=("failure_count",), rows=((0,),), row_count=1)
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            scan_budget_decisions_by_check_id={check.id: _allowed_scan_budget()},
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert check_result.status is CheckStatus.NOT_EXECUTABLE
    assert not check_result.executed
    assert check_result.reason_code is expected_reason
    assert adapter.queries == []


def test_engine_blocks_key_safety_when_scan_budget_blocks_execution(tmp_path: Path) -> None:
    check = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(_key_diff_operation("source_minus_target"),),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)
    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={},
            scan_budget_decisions_by_check_id={
                check.id: classify_scan_budget(
                    ScanBudgetContext(
                        environment=ScanExecutionEnvironment.PRODUCTION,
                        relation_backed=True,
                        bounded=False,
                        estimate_state=ScanEstimateState.UNKNOWN,
                    )
                ),
            },
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert check_result.status is CheckStatus.NOT_EXECUTABLE
    assert not check_result.executed
    assert check_result.reason_code is CheckReason.SCAN_ESTIMATE_UNKNOWN


@pytest.mark.regression_capture("key-safety-shape-blocker-precedence")
def test_engine_preserves_key_safety_shape_blocker_when_scan_budget_decision_is_missing(
    tmp_path: Path,
) -> None:
    row_count = _check(
        check_id="check.ecommerce_recon.customer_revenue.row_count",
        name="row_count",
        check_type="row_count_diff",
        operations=_row_count_operations(),
        required_capabilities=("row_count",),
    )
    missing_keys = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(_key_diff_operation("target_minus_source"),),
        required_capabilities=("key_diff",),
    )
    artifact = _artifact(tmp_path, checks=(row_count, missing_keys))
    contract = _compiled_contract(tmp_path)
    adapter = _RecordingDuckDbAdapter(
        result=QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((4, 4, 0),),
            row_count=1,
        )
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            scan_budget_decisions_by_check_id={},
        ),
    )

    row_count_result, missing_keys_result = result.contract_results[0].check_results
    assert row_count_result.status is CheckStatus.PASS
    assert row_count_result.executed
    assert missing_keys_result.status is CheckStatus.NOT_EXECUTABLE
    assert not missing_keys_result.executed
    assert missing_keys_result.reason_code is CheckReason.UNSUPPORTED_TYPED_OPERATION
    assert missing_keys_result.diagnostics[-1].code == "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    assert len(adapter.queries) == 1


def test_engine_rejects_key_safety_identity_mismatch_before_adapter_lookup(
    tmp_path: Path,
) -> None:
    check = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(
            {
                "type": "key_diff",
                "direction": "source_minus_target",
                "identity": {"kind": "grain", "keys": ["cdc_id"]},
            },
        ),
        required_capabilities=("key_diff",),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={},
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert check_result.status is CheckStatus.NOT_EXECUTABLE
    assert not check_result.executed
    assert check_result.reason_code is CheckReason.UNSUPPORTED_TYPED_OPERATION
    assert check_result.diagnostics[-1].code == "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"


def test_engine_blocks_key_safety_without_compatible_renderer(tmp_path: Path) -> None:
    check = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(_key_diff_operation("source_minus_target"),),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)
    adapter = _OtherAdapter()

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={contract.source.connection: adapter},
            scan_budget_decisions_by_check_id={check.id: _allowed_scan_budget()},
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert check_result.status is CheckStatus.NOT_EXECUTABLE
    assert not check_result.executed
    assert check_result.reason_code is CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT
    assert adapter.queries == []


def test_engine_keeps_key_safety_not_executable_when_required_capability_is_missing(
    tmp_path: Path,
) -> None:
    check = _check(
        check_id="check.ecommerce_recon.customer_revenue.missing_keys",
        name="missing_keys",
        check_type="missing_keys",
        operations=(_key_diff_operation("source_minus_target"),),
        required_capabilities=("key_diff",),
    )
    artifact = _artifact(tmp_path, checks=(check,))
    contract = _compiled_contract(tmp_path)

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
        execution_context=CheckExecutionContext(
            contracts_by_name={contract.contract_name: contract},
            adapters_by_connection={},
            scan_budget_decisions_by_check_id={check.id: _allowed_scan_budget()},
        ),
    )

    check_result = result.contract_results[0].check_results[0]
    assert check_result.status is CheckStatus.NOT_EXECUTABLE
    assert not check_result.executed
    assert check_result.reason_code is CheckReason.MISSING_ENGINE_CAPABILITY


def test_engine_preserves_artifact_and_check_diagnostics(tmp_path: Path) -> None:
    artifact_diagnostic = Diagnostic(
        code="RC_RUNTIME_SAFE_ARTIFACT_DIAGNOSTIC",
        severity=DiagnosticSeverity.ERROR,
        message="Compiled artifact carried a safe diagnostic.",
    )
    check_diagnostic = Diagnostic(
        code="RC_RUNTIME_SAFE_CHECK_DIAGNOSTIC",
        severity=DiagnosticSeverity.ERROR,
        message="Compiled check carried a safe diagnostic.",
    )
    artifact = _artifact(
        tmp_path,
        diagnostics=(artifact_diagnostic,),
        checks=(_check(diagnostics=(check_diagnostic,)),),
    )

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    assert result.diagnostics == (artifact_diagnostic,)
    assert result.contract_results[0].diagnostics == (artifact_diagnostic,)
    assert result.contract_results[0].check_results[0].diagnostics[0] == check_diagnostic


def test_engine_blocks_check_with_missing_prerequisite(tmp_path: Path) -> None:
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=("check.ecommerce_recon.customer_revenue.duplicate_source_keys",),
    )
    artifact = _artifact(tmp_path, checks=(dependent,))

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    check = result.contract_results[0].check_results[0]
    assert result.status is RunStatus.BLOCKED
    assert check.status is CheckStatus.BLOCKED
    assert check.reason_code is CheckReason.PREREQUISITE_MISSING
    assert check.blocked_by == ("check.ecommerce_recon.customer_revenue.duplicate_source_keys",)
    assert check.diagnostics[0].code == BLOCKED_BY_PREREQUISITE
    assert check.diagnostics[0].resource_name == "customer_revenue.value_match"


def test_engine_blocks_check_when_prerequisite_errors(tmp_path: Path) -> None:
    prerequisite = _check(
        check_id="check.ecommerce_recon.customer_revenue.duplicate_source_keys",
        name="duplicate_source_keys",
    )
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=(prerequisite.id,),
    )
    dispatcher = _RaisingDispatcher(failing_check_id=prerequisite.id)
    artifact = _artifact(tmp_path, checks=(prerequisite, dependent))

    result = CheckEngine(dispatcher=dispatcher).run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    prerequisite_result, dependent_result = result.contract_results[0].check_results
    assert prerequisite_result.status is CheckStatus.ERROR
    assert prerequisite_result.diagnostics[0].code == CHECK_ENGINE_INTERNAL_ERROR
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.reason_code is CheckReason.PREREQUISITE_ERROR
    assert dependent_result.blocked_by == (prerequisite.id,)


def test_engine_blocks_check_when_later_prerequisite_errors(tmp_path: Path) -> None:
    prerequisite = _check(
        check_id="check.ecommerce_recon.customer_revenue.duplicate_source_keys",
        name="duplicate_source_keys",
    )
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=(prerequisite.id,),
    )
    dispatcher = _RaisingDispatcher(failing_check_id=prerequisite.id)
    artifact = _artifact(tmp_path, checks=(dependent, prerequisite))

    result = CheckEngine(dispatcher=dispatcher).run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    dependent_result, prerequisite_result = result.contract_results[0].check_results
    assert prerequisite_result.status is CheckStatus.ERROR
    assert prerequisite_result.diagnostics[0].code == CHECK_ENGINE_INTERNAL_ERROR
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.reason_code is CheckReason.PREREQUISITE_ERROR
    assert dependent_result.blocked_by == (prerequisite.id,)


def test_engine_blocks_check_when_prerequisite_is_blocked(tmp_path: Path) -> None:
    prerequisite = _check(
        check_id="check.ecommerce_recon.customer_revenue.duplicate_source_keys",
        name="duplicate_source_keys",
        prerequisites=("check.ecommerce_recon.customer_revenue.null_source_keys",),
    )
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=(prerequisite.id,),
    )
    artifact = _artifact(tmp_path, checks=(dependent, prerequisite))

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    dependent_result, prerequisite_result = result.contract_results[0].check_results
    assert prerequisite_result.status is CheckStatus.BLOCKED
    assert prerequisite_result.reason_code is CheckReason.PREREQUISITE_MISSING
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.reason_code is CheckReason.PREREQUISITE_MISSING
    assert dependent_result.blocked_by == (prerequisite.id,)


def test_engine_blocks_check_when_prerequisite_is_not_executable(tmp_path: Path) -> None:
    prerequisite = _check(
        check_id="check.ecommerce_recon.customer_revenue.duplicate_source_keys",
        name="duplicate_source_keys",
    )
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=(prerequisite.id,),
    )
    artifact = _artifact(tmp_path, checks=(dependent, prerequisite))

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    dependent_result, prerequisite_result = result.contract_results[0].check_results
    assert prerequisite_result.status is CheckStatus.NOT_EXECUTABLE
    assert prerequisite_result.reason_code is CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.reason_code is CheckReason.PREREQUISITE_NOT_EXECUTABLE
    assert dependent_result.blocked_by == (prerequisite.id,)


def test_engine_reports_multiple_missing_prerequisites_once(tmp_path: Path) -> None:
    dependent = _check(
        check_id="check.ecommerce_recon.customer_revenue.value_match",
        name="value_match",
        check_type="value_match",
        prerequisites=(
            "check.ecommerce_recon.customer_revenue.null_source_keys",
            "check.ecommerce_recon.customer_revenue.duplicate_source_keys",
            "check.ecommerce_recon.customer_revenue.null_source_keys",
        ),
    )
    artifact = _artifact(tmp_path, checks=(dependent,))

    result = CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    dependent_result = result.contract_results[0].check_results[0]
    assert dependent_result.status is CheckStatus.BLOCKED
    assert dependent_result.reason_code is CheckReason.PREREQUISITE_MISSING
    assert dependent_result.blocked_by == (
        "check.ecommerce_recon.customer_revenue.null_source_keys",
        "check.ecommerce_recon.customer_revenue.duplicate_source_keys",
    )


def test_engine_sanitizes_unexpected_dispatch_error(tmp_path: Path) -> None:
    artifact = _artifact(tmp_path, checks=(_check(),))

    result = CheckEngine(dispatcher=_RaisingDispatcher()).run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    check = result.contract_results[0].check_results[0]
    assert result.status is RunStatus.ERROR
    assert check.status is CheckStatus.ERROR
    assert not check.executed
    assert check.reason_code is None
    assert check.diagnostics[0].code == CHECK_ENGINE_INTERNAL_ERROR
    assert "super-secret" not in check.diagnostics[0].message


def test_engine_empty_artifacts_aggregate_to_no_checks() -> None:
    result = CheckEngine().run(
        (),
        run_id="run-001",
        project_name="ecommerce_recon",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    assert result.project_name == "ecommerce_recon"
    assert result.status is RunStatus.NO_CHECKS
    assert result.contract_results == ()


def test_engine_writes_no_generated_outputs(tmp_path: Path) -> None:
    target_path = tmp_path / "target"
    reports_path = tmp_path / "reports"
    state_path = tmp_path / "state"
    artifact = _artifact(target_path, checks=(_check(),))

    CheckEngine().run(
        (artifact,),
        run_id="run-001",
        started_at="2026-06-11T10:00:00Z",
        finished_at="2026-06-11T10:00:01Z",
    )

    assert not (target_path / "run_results.json").exists()
    assert not (target_path / "failures").exists()
    assert not reports_path.exists()
    assert not state_path.exists()


class _RaisingDispatcher:
    def __init__(self, failing_check_id: str | None = None) -> None:
        self.failing_check_id = failing_check_id

    def dispatch(self, check: LoadedCompiledCheck) -> CheckResult:
        if self.failing_check_id is None or check.id == self.failing_check_id:
            raise RuntimeError("super-secret database error")
        message = "Check belongs to a later execution phase."
        return CheckResult(
            check_id=check.id,
            name=check.name,
            check_type=check.check_type,
            contract_name=check.contract_name,
            status=CheckStatus.NOT_EXECUTABLE,
            executed=False,
            reason_code=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
            message=message,
            diagnostics=(
                Diagnostic(
                    code="RC_RUNTIME_CHECK_NOT_EXECUTABLE",
                    severity=DiagnosticSeverity.ERROR,
                    message=message,
                ),
            ),
        )


def _artifact(
    tmp_path: Path,
    *,
    checks: tuple[LoadedCompiledCheck, ...],
    diagnostics: tuple[Diagnostic, ...] = (),
) -> LoadedCompiledChecksArtifact:
    return LoadedCompiledChecksArtifact(
        path=tmp_path / "target" / "compiled_checks" / "customer_revenue.yml",
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contract_id="contract.ecommerce_recon.customer_revenue",
        contract_name="customer_revenue",
        source_file="contracts/customer_revenue.yml",
        checks=checks,
        diagnostics=diagnostics,
    )


def _check(
    *,
    check_id: str = "check.ecommerce_recon.customer_revenue.row_count_diff",
    name: str = "row_count_diff",
    check_type: str = "row_count_diff",
    prerequisites: tuple[str, ...] = (),
    diagnostics: tuple[Diagnostic, ...] = (),
    rendering_status: str | None = None,
    operations: tuple[dict[str, object], ...] | None = None,
    required_capabilities: tuple[str, ...] = (),
) -> LoadedCompiledCheck:
    return LoadedCompiledCheck(
        id=check_id,
        name=name,
        check_type=check_type,
        contract_name="customer_revenue",
        plan=LoadedCheckPlan(
            id=f"plan.ecommerce_recon.customer_revenue.{name}",
            operations=operations
            if operations is not None
            else ({"type": "row_count", "side": "source"},),
            required_capabilities=required_capabilities,
        ),
        prerequisites=prerequisites,
        rendering_status=rendering_status,
        diagnostics=diagnostics,
        payload={
            "identity": {
                "kind": "none",
                "keys": [],
            }
        },
    )


def _row_count_operations() -> tuple[dict[str, object], ...]:
    return (
        {"type": "row_count", "side": "source"},
        {"type": "row_count", "side": "target"},
        {"type": "compare_counts"},
    )


def _key_diff_operation(direction: str) -> dict[str, object]:
    return {
        "type": "key_diff",
        "direction": direction,
        "identity": {"kind": "grain", "keys": ["customer_id"]},
    }


def _duplicate_key_operation(side: str) -> dict[str, object]:
    return {
        "type": "duplicate_key",
        "side": side,
        "identity": {"kind": "grain", "keys": ["customer_id"]},
    }


def _allowed_scan_budget() -> ScanBudgetDecision:
    return classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.LOCAL_DEV,
            relation_backed=True,
            bounded=True,
            estimate_state=ScanEstimateState.UNKNOWN,
        )
    )


def _compiled_contract(
    tmp_path: Path,
    *,
    source_connection: str = "warehouse",
    target_connection: str = "warehouse",
) -> LoadedCompiledContractArtifact:
    return LoadedCompiledContractArtifact(
        path=tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml",
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contract_id="contract.ecommerce_recon.customer_revenue",
        contract_name="customer_revenue",
        source_file="contracts/customer_revenue.yml",
        source=LoadedCompiledEndpoint(
            connection=source_connection,
            relation="qa.source_customers",
        ),
        target=LoadedCompiledEndpoint(
            connection=target_connection,
            relation="qa.target_customers",
        ),
        grain_keys=("customer_id",),
    )


class _RecordingDuckDbAdapter(BaseAdapter):
    adapter_type = "duckdb"
    adapter_version = "test"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(
        self,
        *,
        connection: ConnectionConfig | None = None,
        result: QueryResult | None = None,
        results: tuple[QueryResult, ...] | None = None,
    ) -> None:
        super().__init__(connection=connection or ConnectionConfig(name="warehouse", type="duckdb"))
        default_result = result or QueryResult(
            columns=("source_row_count", "target_row_count", "row_count_diff"),
            rows=((1, 1, 0),),
            row_count=1,
        )
        self.results = list(results) if results is not None else [default_result]
        self.queries: list[str] = []

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute(self, query: str) -> QueryResult:
        self.queries.append(query)
        if len(self.results) > 1:
            return self.results.pop(0)
        return self.results[0]

    def relation_exists(self, relation: Relation) -> bool:
        return False

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return ()

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                "relations": CapabilitySupport.FULL,
                "queries": CapabilitySupport.UNSUPPORTED,
                "cte_support": CapabilitySupport.FULL,
                "row_count": CapabilitySupport.FULL,
            }
        )


class _OtherAdapter(_RecordingDuckDbAdapter):
    adapter_type = "otherdb"
