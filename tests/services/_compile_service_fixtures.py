from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import yaml

from recon_core.adapters import (
    AdapterCapabilities,
    AdapterResolutionResult,
    BaseAdapter,
    CapabilitySupport,
    QueryResult,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig
from recon_core.services import ServiceResult


class FakeAdapter(BaseAdapter):
    adapter_type = "fake"
    adapter_version = "0.0.test"
    supported_adapter_api_version = "1"

    def connect(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def execute(self, query: str) -> QueryResult:
        raise NotImplementedError

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities({})


class FakeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=FakeAdapter(connection=connection))


class DiagnosticAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=FakeAdapter(connection=connection),
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_WITH_DIAGNOSTIC",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter factory returned an adapter with a setup diagnostic.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Fix the adapter factory setup diagnostic.",
                ),
            ),
        )


class ConnectionDiagnosticAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_CONNECTION_SETUP_FAILED",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Connection `{connection.name}` setup failed.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Fix the adapter setup failure.",
                ),
            )
        )


class LeakyApiAdapter(FakeAdapter):
    adapter_type = "leaky_api"
    supported_adapter_api_version = "password=super-secret"


class LeakyApiAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=LeakyApiAdapter(connection=connection))


class RaisingApiVersion:
    def __get__(self, instance: object, owner: object | None = None) -> str:
        raise AttributeError("password=super-secret")


class MissingApiVersionAdapter(FakeAdapter):
    adapter_type = "missing_api"
    supported_adapter_api_version = cast(str, RaisingApiVersion())


class MissingApiVersionAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=MissingApiVersionAdapter(connection=connection))


class NonStringAdapterTypeAdapter(FakeAdapter):
    adapter_type = cast(Any, 123)


class NonStringAdapterTypeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=NonStringAdapterTypeAdapter(connection=connection))


class RaisingAdapterType:
    def __get__(self, instance: object, owner: object | None = None) -> str:
        raise RuntimeError("password=super-secret")


class RaisingAdapterTypeAdapter(FakeAdapter):
    adapter_type = cast(str, RaisingAdapterType())


class RaisingAdapterTypeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=RaisingAdapterTypeAdapter(connection=connection))


class MismatchedAdapterTypeAdapter(FakeAdapter):
    adapter_type = "duckdb"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                "relations": CapabilitySupport.FULL,
                "row_count": CapabilitySupport.FULL,
                "aggregate": CapabilitySupport.FULL,
                "grouped_aggregate": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
            }
        )


class MismatchedAdapterTypeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=MismatchedAdapterTypeAdapter(connection=connection))


class CapabilityRaisingDuckDbAdapter(FakeAdapter):
    adapter_type = "duckdb"

    def capabilities(self) -> AdapterCapabilities:
        raise ValueError(f"password={self.connection.config.get('password')}")


class CapabilityRaisingDuckDbAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=CapabilityRaisingDuckDbAdapter(connection=connection)
        )


class InvalidCapabilityDuckDbAdapter(FakeAdapter):
    adapter_type = "duckdb"

    def capabilities(self) -> AdapterCapabilities:
        invalid_support: dict[str, Any] = {
            "relations": CapabilitySupport.FULL,
            "row_count": "wat",
        }
        return AdapterCapabilities(invalid_support)


class InvalidCapabilityDuckDbAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=InvalidCapabilityDuckDbAdapter(connection=connection)
        )


class StepCapabilityUnsupportedDuckDbAdapter(FakeAdapter):
    adapter_type = "duckdb"

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                "relations": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.UNSUPPORTED,
                "row_count": CapabilitySupport.FULL,
                "aggregate": CapabilitySupport.FULL,
                "grouped_aggregate": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
            }
        )


class StepCapabilityUnsupportedDuckDbAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=StepCapabilityUnsupportedDuckDbAdapter(connection=connection)
        )


class EmptyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult()


class InvalidResolutionAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return None  # type: ignore[return-value]


class MalformedDiagnosticsAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=cast(tuple[Diagnostic, ...], ("not-a-diagnostic",))
        )


class MalformedDiagnosticFieldsAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_MALFORMED_DIAGNOSTIC_FIELD",
                    severity=cast(Any, "error"),
                    message="Malformed diagnostic field.",
                ),
            )
        )


class RaisingAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        raise ValueError(f"password={connection.config.get('password')}")


class LeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        f"Connection database={connection.config.get('database')} "
                        f"password={connection.config.get('password')}"
                    ),
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint=f"Do not leak database {connection.config.get('database')}.",
                ),
            )
        )


class DsnFragmentLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_DSN_FRAGMENT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter connection failed for password super-secret.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the profile DSN.",
                ),
            )
        )


class CodeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code=str(connection.config.get("password")),
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class NumericCodeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code=str(connection.config.get("port")),
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class EmbeddedCodeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code=f"RC{connection.config.get('password')}LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class EmbeddedConfigKeyCodeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RCPASSWORDLEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class EmbeddedNumericCodeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code=f"RC{connection.config.get('port')}LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class NumericValueLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_NUMERIC_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=str(connection.config.get("password")),
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class NumericFieldLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_NUMERIC_FIELD_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    line=int(str(connection.config.get("password"))),
                    column=int(str(connection.config.get("password"))),
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class ShortNumericFieldLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_SHORT_NUMERIC_FIELD_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    line=int(str(connection.config.get("port"))),
                    column=int(str(connection.config.get("port"))),
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class ShortNumericTextLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        port = str(connection.config.get("port"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_SHORT_NUMERIC_TEXT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter setup failed at endpoint {port}.",
                    resource_type="adapter",
                    resource_name=port,
                    hint=f"Inspect endpoint {port}.",
                ),
            )
        )


class DecimalShortNumericTextLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        port = f"{int(str(connection.config.get('port'))):.1f}"
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_DECIMAL_SHORT_NUMERIC_TEXT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter setup failed at endpoint {port}.",
                    resource_type=f"endpoint-{port}",
                    resource_name=port,
                    path=f"adapter://endpoint/{port}",
                    hint=f"Inspect endpoint {port}.",
                ),
            )
        )


class IntegerEquivalentQuotedDecimalTextLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        port = str(int(Decimal(str(connection.config.get("port")))))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_INTEGER_EQUIVALENT_QUOTED_DECIMAL_TEXT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter setup failed at endpoint {port}.",
                    resource_type=f"endpoint-{port}",
                    resource_name=port,
                    path=f"adapter://endpoint/{port}",
                    hint=f"Inspect endpoint {port}.",
                ),
            )
        )


class FormattedNumericTextLeakyAdapterFactory:
    def __init__(self, *, emitted_port: str) -> None:
        self.emitted_port = emitted_port

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_FORMATTED_NUMERIC_TEXT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter setup failed at endpoint {self.emitted_port}.",
                    resource_type=f"endpoint-{self.emitted_port}",
                    resource_name=self.emitted_port,
                    path=f"adapter://endpoint/{self.emitted_port}",
                    hint=f"Inspect endpoint {self.emitted_port}.",
                ),
            )
        )


class ShortNumericAdapterTypeAdapter(FakeAdapter):
    adapter_type = "12"


class ShortNumericAdapterTypeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=ShortNumericAdapterTypeAdapter(connection=connection)
        )


class CaseVariantLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        password = str(connection.config.get("password"))
        database = str(connection.config.get("database"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_CASE_VARIANT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=(f"PASSWORD={password.casefold()} DATABASE={database.upper()}"),
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint=f"Check DATABASE {database.upper()}.",
                ),
            )
        )


class ResourceTypeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        password = str(connection.config.get("password"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_RESOURCE_TYPE_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter failed while resolving the selected connection.",
                    resource_type=f"PASSWORD={password.casefold()}",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class MessageAndResourceTypeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        password = str(connection.config.get("password"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_MESSAGE_AND_RESOURCE_TYPE_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter failed with password={password.casefold()}.",
                    resource_type=f"PASSWORD={password.casefold()}",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class LeakyRenderPhaseAdapter(FakeAdapter):
    adapter_type = "password=super-secret"


class LeakyRenderPhaseAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=LeakyRenderPhaseAdapter(connection=connection))


def write_project(
    project_root: Path,
    *,
    project_name: str = "ecommerce_recon",
    check_pack_paths: tuple[str, ...] | None = None,
    profile: str | None = None,
) -> None:
    check_pack_paths_yaml = _path_list_yaml("check-pack-paths", check_pack_paths)
    profile_yaml = f"profile: {profile}\n" if profile is not None else ""
    project_root.joinpath("contracts").mkdir(exist_ok=True)
    project_root.joinpath("recon_project.yml").write_text(
        f"""
name: {project_name}
version: 0.1.0
config-version: 1
{profile_yaml}
contract-paths:
  - contracts
{check_pack_paths_yaml}
target-path: target
""".lstrip(),
        encoding="utf-8",
    )


def write_profiles(
    project_root: Path,
    *,
    connection_type: str = "duckdb",
    use_distinct_databases: bool = False,
    database: str | None = None,
    include_password: bool = False,
    password: str = "super-secret",
    port: int | str | None = None,
) -> None:
    legacy_database = database or ("legacy.duckdb" if use_distinct_databases else "local.duckdb")
    warehouse_database = database or (
        "warehouse.duckdb" if use_distinct_databases else "local.duckdb"
    )
    password_yaml = f"            password: {password}\n" if include_password else ""
    port_yaml = f"            port: {port}\n" if port is not None else ""
    profiles_path = project_root / "connections" / "profiles.yml"
    profiles_path.parent.mkdir()
    profiles_path.write_text(
        f"""
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: {connection_type}
            database: {legacy_database}
{password_yaml.rstrip()}
{port_yaml.rstrip()}
          warehouse:
            type: {connection_type}
            database: {warehouse_database}
{password_yaml.rstrip()}
{port_yaml.rstrip()}
""".lstrip(),
        encoding="utf-8",
    )


def _assert_render_sql_blocked_artifact(project_root: Path, diagnostic_code: str) -> None:
    checks_artifact = yaml.safe_load(
        (project_root / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert all(check["rendering"]["status"] == "blocked" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert {
        diagnostic["code"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {diagnostic_code}


def _assert_distinct_connection_diagnostic_messages(
    diagnostics: tuple[Diagnostic, ...],
    *,
    unscoped_message: str,
) -> None:
    assert {diagnostic.message for diagnostic in diagnostics} == {
        f"Connection `legacy`: {unscoped_message}",
        f"Connection `warehouse`: {unscoped_message}",
    }


def _assert_blocked_artifact_includes_messages(
    project_root: Path,
    expected_messages: set[str],
) -> None:
    checks_artifact = yaml.safe_load(
        (project_root / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    artifact_messages = {
        diagnostic["message"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    }

    assert expected_messages <= artifact_messages


def _public_diagnostic_and_rendering_output(
    result: ServiceResult,
    checks_artifact: Mapping[str, Any],
) -> str:
    return cast(
        str,
        yaml.safe_dump(
            {
                "service": [diagnostic.to_dict() for diagnostic in result.diagnostics],
                "checks": [
                    {
                        "rendering": check["rendering"],
                        "diagnostics": check["diagnostics"],
                    }
                    for check in checks_artifact["checks"]
                ],
            },
            sort_keys=False,
        ),
    )


def _path_list_yaml(field_name: str, paths: tuple[str, ...] | None) -> str:
    if paths is None:
        return ""
    path_items = "\n".join(f"  - {path}" for path in paths)
    return f"{field_name}:\n{path_items}"


def write_contract(
    project_root: Path,
    *,
    name: str = "customer_revenue",
    file_name: str = "customer_revenue.yml",
    source_connection: str = "legacy",
    target_connection: str = "warehouse",
    include_grain: bool = True,
    tolerance_policy: str | None = None,
    nulls: dict[str, object] | None = None,
    source_query: str | None = None,
) -> None:
    grain_yaml = (
        """
grain:
  keys:
    - customer_id
    - month
"""
        if include_grain
        else ""
    )
    tolerance_policy_yaml = (
        yaml.safe_dump({"tolerance_policy": tolerance_policy}, sort_keys=False)
        if tolerance_policy is not None
        else ""
    )
    nulls_yaml = yaml.safe_dump({"nulls": nulls}, sort_keys=False) if nulls is not None else ""
    source_endpoint_yaml = (
        f"  query: {source_query}\n"
        if source_query is not None
        else "  relation: qa.customer_source\n"
    )
    project_root.joinpath("contracts", file_name).write_text(
        f"""
version: 1
name: {name}
source:
  connection: {source_connection}
{source_endpoint_yaml}target:
  connection: {target_connection}
  relation: qa.customer_target
{grain_yaml}metrics:
  - name: total_revenue
    type: sum
    column: revenue
checks:
  use:
    - recon_core.basic_equivalence
sampling:
  default_policy: full
{tolerance_policy_yaml}{nulls_yaml}
""".lstrip(),
        encoding="utf-8",
    )
