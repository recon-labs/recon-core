from collections.abc import Mapping
from typing import Any, cast

import pytest

from recon_core.adapters import (
    AdapterCapabilities,
    CapabilitySupport,
    ConnectionConfig,
    Relation,
    RenderedSql,
)
from recon_core.adapters.duckdb import DuckDbAdapter, DuckDbSqlRenderer
from recon_core.adapters.rendering import render_check_sql
from recon_core.compiler import compile_project
from recon_core.compiler.models import CompiledCheck, CompiledContractArtifact
from recon_core.parser.contracts import AuthoredContract, AuthoredEndpoint
from recon_core.parser.models import SourceLocation


def test_render_check_sql_validates_required_capabilities_before_rendering() -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=DuckDbSqlRenderer(),
        capabilities=AdapterCapabilities({"relations": CapabilitySupport.FULL}),
    )

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "row_count" in result.diagnostics[0].message


def test_render_check_sql_sanitizes_capability_declaration_exceptions() -> None:
    compiled_contract, check = compiled_row_count_check()

    class SecretLeakingCapabilityAdapter(DuckDbAdapter):
        def capabilities(self) -> AdapterCapabilities:
            raise ValueError(f"password={self.connection.config.get('password')}")

    adapter = SecretLeakingCapabilityAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"password": "super-secret"},
        )
    )

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=DuckDbSqlRenderer(),
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_DECLARATION_FAILED"
    ]
    assert "ValueError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_render_check_sql_blocks_query_endpoints_without_leaking_query_text_or_secrets() -> None:
    compiled_contract, check = compiled_row_count_check(
        source=AuthoredEndpoint(connection="legacy", query="select * from secret_customer_source"),
    )
    adapter = DuckDbAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"password": "super-secret"},
        )
    )

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=DuckDbSqlRenderer(),
    )

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "source" in diagnostic_text
    assert "secret_customer_source" not in diagnostic_text
    assert "super-secret" not in diagnostic_text


def test_render_check_sql_renders_in_memory_without_leaking_connection_payloads() -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"password": "super-secret"},
        )
    )

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=DuckDbSqlRenderer(),
    )

    assert result.succeeded
    assert result.diagnostics == ()
    assert [step.operation_type for step in result.sql] == [
        "row_count",
        "row_count",
        "compare_counts",
    ]
    rendered_sql = "\n".join(step.sql for step in result.sql)
    assert '"qa"."customer_source"' in rendered_sql
    assert '"qa"."customer_target"' in rendered_sql
    assert "super-secret" not in rendered_sql


def test_render_check_sql_sanitizes_renderer_exception_diagnostics() -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"password": "super-secret"},
        )
    )

    class SecretLeakingRenderer(DuckDbSqlRenderer):
        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            raise ValueError("password=super-secret")

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=SecretLeakingRenderer(),
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_OPERATION_RENDER_FAILED"
    ]
    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"
    assert "ValueError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_render_check_sql_rejects_incompatible_adapter_api_before_rendering() -> None:
    compiled_contract, check = compiled_row_count_check()

    class IncompatibleApiAdapter(DuckDbAdapter):
        supported_adapter_api_version = "999"

    class RendererShouldNotRun(DuckDbSqlRenderer):
        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            raise AssertionError("render_plan should not run for incompatible adapter APIs")

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=IncompatibleApiAdapter(
            connection=ConnectionConfig(name="warehouse", type="duckdb")
        ),
        renderer=RendererShouldNotRun(),
    )

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_API_VERSION_UNSUPPORTED"
    ]


def test_render_check_sql_rejects_mismatched_renderer_type_before_rendering() -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))

    class MismatchedRenderer(DuckDbSqlRenderer):
        adapter_type = "postgres"

        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            raise AssertionError("render_plan should not run for mismatched renderers")

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=MismatchedRenderer(),
    )

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RENDERER_TYPE_MISMATCH"
    ]


def test_render_check_sql_rejects_malformed_renderer_type_before_rendering() -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))

    class EmptyRendererType(DuckDbSqlRenderer):
        adapter_type = ""

        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            raise AssertionError("render_plan should not run for malformed renderers")

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=EmptyRendererType(),
    )

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RENDERER_METADATA_INVALID"
    ]


def test_render_check_sql_sanitizes_raising_renderer_type_before_rendering() -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))

    class RaisingRendererType:
        def __get__(self, instance: object, owner: object | None = None) -> str:
            raise RuntimeError("password=super-secret")

    class RaisingRenderer(DuckDbSqlRenderer):
        adapter_type = cast(str, RaisingRendererType())

        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            raise AssertionError("render_plan should not run for malformed renderers")

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=RaisingRenderer(),
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RENDERER_METADATA_INVALID"
    ]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_render_check_sql_rejects_empty_renderer_output() -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))

    class EmptyRenderer(DuckDbSqlRenderer):
        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            return ()

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=EmptyRenderer(),
    )

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RENDERED_SQL_EMPTY"
    ]


@pytest.mark.parametrize(
    "rendered_sql",
    [
        pytest.param((cast(RenderedSql, object()),), id="non-rendered-sql-step"),
        pytest.param(
            (
                RenderedSql(
                    sql=cast(str, object()),
                    operation_type="row_count",
                    step_name="00-row_count-source",
                ),
            ),
            id="non-string-sql",
        ),
        pytest.param(
            (
                RenderedSql(
                    sql="",
                    operation_type="row_count",
                    step_name="00-row_count-source",
                ),
            ),
            id="empty-sql",
        ),
        pytest.param(
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="",
                    step_name="00-row_count-source",
                ),
            ),
            id="empty-operation-type",
        ),
        pytest.param(
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="",
                ),
            ),
            id="empty-step-name",
        ),
        pytest.param(
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="../outside",
                ),
            ),
            id="path-like-step-name",
        ),
        pytest.param(
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="same",
                ),
                RenderedSql(
                    sql="select 2",
                    operation_type="row_count",
                    step_name="same",
                ),
            ),
            id="duplicate-step-name",
        ),
        pytest.param(
            (
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
            id="case-insensitive-duplicate-step-name",
        ),
    ],
)
def test_render_check_sql_rejects_malformed_renderer_output(
    rendered_sql: tuple[object, ...],
) -> None:
    compiled_contract, check = compiled_row_count_check()
    adapter = DuckDbAdapter(connection=ConnectionConfig(name="warehouse", type="duckdb"))

    class MalformedRenderer(DuckDbSqlRenderer):
        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            return cast(tuple[RenderedSql, ...], rendered_sql)

    result = render_check_sql(
        contract=compiled_contract,
        check=check,
        adapter=adapter,
        renderer=MalformedRenderer(),
    )

    assert not result.succeeded
    assert result.sql == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_OPERATION_RENDER_FAILED"
    ]


def compiled_row_count_check(
    *,
    source: AuthoredEndpoint | None = None,
    target: AuthoredEndpoint | None = None,
) -> tuple[CompiledContractArtifact, CompiledCheck]:
    contract = AuthoredContract(
        name="customer_revenue",
        version=1,
        source=source or AuthoredEndpoint(connection="legacy", relation="qa.customer_source"),
        target=target or AuthoredEndpoint(connection="warehouse", relation="qa.customer_target"),
        source_location=SourceLocation(path="contracts/customer_revenue.yml"),
        grain={"keys": ["customer_id"]},
        checks={"use": ["recon_core.basic_equivalence"]},
    )
    compilation = compile_project(
        project_name="ecommerce_recon",
        project_version="0.1.0",
        contracts=(contract,),
    )
    assert compilation.succeeded
    compiled = compilation.contracts[0]
    row_count_check = next(
        check for check in compiled.checks_artifact.checks if check.name == "row_count_diff"
    )
    return compiled.contract_artifact, row_count_check
