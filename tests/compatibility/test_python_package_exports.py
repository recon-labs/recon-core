from __future__ import annotations

import importlib
import subprocess
import sys
import textwrap
from collections.abc import Iterable

import pytest

KNOWN_EXPORT_CATEGORIES = {
    "adapter_testkit_pre_alpha_surface",
    "compatibility_convenience_reexport",
    "concrete_adapter_convenience_surface",
    "public_framework_surface",
}

PACKAGE_EXPORTS: dict[str, dict[str, tuple[str, ...]]] = {
    "recon_core": {
        "public_framework_surface": (
            "__version__",
            "get_version",
        ),
    },
    "recon_core.diagnostics": {
        "public_framework_surface": (
            "Diagnostic",
            "DiagnosticDict",
            "DiagnosticSeverity",
        ),
    },
    "recon_core.adapters": {
        "adapter_testkit_pre_alpha_surface": (
            "ADAPTER_API_VERSION",
            "ADAPTER_API_VERSION_UNSUPPORTED",
            "ADAPTER_CAPABILITY_DECLARATION_FAILED",
            "ADAPTER_CAPABILITY_UNSUPPORTED",
            "ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
            "ADAPTER_METADATA_INVALID",
            "ADAPTER_RESOLUTION_FAILED",
            "ADAPTER_INVALID_RELATION",
            "ADAPTER_OPERATION_RENDER_FAILED",
            "ADAPTER_QUERY_ENDPOINT_UNSUPPORTED",
            "ADAPTER_RENDERED_SQL_EMPTY",
            "ADAPTER_RENDERER_METADATA_INVALID",
            "ADAPTER_RENDERER_TYPE_MISMATCH",
            "ADAPTER_TYPE_MISMATCH",
            "ADAPTER_UNKNOWN_TYPE",
            "AdapterCapabilities",
            "AdapterFactory",
            "AdapterRegistry",
            "AdapterResolutionResult",
            "BaseAdapter",
            "CapabilitySupport",
            "ColumnMetadata",
            "ConnectionConfig",
            "QueryResult",
            "Relation",
            "RelationMetadataAdapter",
            "RenderedCheckSql",
            "RenderedSql",
            "RuntimeAdapterSetupResult",
            "SqlRenderer",
            "default_adapter_registry",
            "prepare_runtime_adapter",
            "render_check_sql",
            "validate_adapter_api_compatibility",
            "validate_required_capabilities",
        ),
    },
    "recon_core.adapters.duckdb": {
        "concrete_adapter_convenience_surface": (
            "ADAPTER_CLOSE_FAILED",
            "ADAPTER_CONNECTION_FAILED",
            "ADAPTER_DEPENDENCY_MISSING",
            "ADAPTER_QUERY_FAILED",
            "AdapterLifecycleError",
            "DuckDbAdapter",
            "DuckDbAdapterFactory",
            "DuckDbSqlRenderer",
        ),
    },
    "recon_core.check_engine": {
        "compatibility_convenience_reexport": (
            "ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED",
            "BLOCKED_BY_PREREQUISITE",
            "CHECK_ENGINE_INTERNAL_ERROR",
            "CHECK_NOT_EXECUTABLE",
            "MISSING_ENGINE_CAPABILITY",
            "ROW_COUNT_RESULT_INVALID",
            "UNSUPPORTED_CHECK_TYPE",
            "UNSUPPORTED_EXECUTION_PLACEMENT",
            "UNSUPPORTED_MATERIALIZATION_POLICY",
            "UNSUPPORTED_TYPED_OPERATION",
            "CheckDispatcher",
            "CheckEngine",
            "CheckExecutionContext",
            "CheckReason",
            "CheckResult",
            "CheckResultDict",
            "CheckStatus",
            "ContractResult",
            "ContractResultDict",
            "RunResult",
            "RunResultDict",
            "RunStatus",
            "aggregate_check_status",
            "aggregate_contract_status",
            "execute_row_count_check",
            "is_supported_row_count_plan_shape",
        ),
    },
    "recon_core.compiler": {
        "compatibility_convenience_reexport": (
            "AdapterCapability",
            "BASIC_EQUIVALENCE_CHECK_PACK_NAME",
            "BlockingPolicy",
            "BlockingPolicyValue",
            "CDC_CONFIG_REQUIRED",
            "COMPILED_ARTIFACT_FILENAME_COLLISION",
            "COMPILED_ARTIFACT_VERSION",
            "CdcValidationResult",
            "CheckOrigin",
            "CheckOriginKind",
            "CheckPackExpansionResult",
            "CheckPlan",
            "CheckPlanDict",
            "CheckRequirements",
            "ColumnCategory",
            "ColumnDeclaration",
            "ColumnRegistry",
            "ColumnValidationResult",
            "CompiledArtifactType",
            "CompiledCheck",
            "CompiledCheckDict",
            "CompiledCheckType",
            "CompiledChecksArtifact",
            "CompiledChecksArtifactDict",
            "CompiledContractArtifact",
            "CompiledContractArtifactDict",
            "CompiledContractPolicies",
            "CompiledContractPoliciesDict",
            "CompiledContractReference",
            "CompiledContractReferenceDict",
            "CompiledEndpoint",
            "CompiledEndpointDict",
            "CompiledMetric",
            "CompiledMetricDict",
            "CompiledProject",
            "CompiledProjectDict",
            "ContractCompilationArtifacts",
            "DUPLICATE_CHECK_PACK_INVOCATION",
            "DUPLICATE_COLUMN_NAME",
            "DUPLICATE_COMPILED_CHECK",
            "DUPLICATE_METRIC_NAME",
            "INCOMPATIBLE_COLUMN_TYPE",
            "INVALID_CDC_KEYS",
            "INVALID_CHECK_PACK_USE",
            "INVALID_COLUMN_DECLARATION",
            "INVALID_COLUMN_SELECTION",
            "INVALID_GRAIN_KEYS",
            "INVALID_METRIC",
            "INVALID_NORMALIZATION",
            "INVALID_NULL_POLICY",
            "INVALID_NULL_SENTINEL",
            "INVALID_REGEX_NORMALIZATION",
            "INVALID_SAMPLING",
            "INVALID_STABLE_ID_PART",
            "INVALID_TOLERANCE",
            "Identity",
            "IdentityDict",
            "IdentityKind",
            "KeyDiffDirection",
            "MetricCompilationResult",
            "NO_COMPILED_CHECKS",
            "NO_CONTRACTS_FOUND",
            "OperationSide",
            "OperationType",
            "PolicyValidationResult",
            "ProjectCompilationResult",
            "Rendering",
            "RenderingStatus",
            "ResolvedSampling",
            "ResolvedSamplingDict",
            "SUPPORTED_METRIC_TYPES",
            "STABLE_ID_PART_HINT",
            "SamplingValidationResult",
            "TypedOperation",
            "TypedOperationDict",
            "UNDECLARED_COLUMN_REFERENCE",
            "UNKNOWN_CHECK_PACK",
            "UNKNOWN_METRIC_FIELD",
            "UNSUPPORTED_CHECK_PACK_CONFIG",
            "UNSUPPORTED_EXPLICIT_CHECKS",
            "UNSUPPORTED_METRIC_TYPE",
            "VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS",
            "build_check_id",
            "build_contract_id",
            "build_plan_id",
            "compile_metrics",
            "compile_project",
            "expand_basic_equivalence",
            "expand_check_pack",
            "is_valid_stable_id_part",
            "validate_cdc_policy",
            "validate_columns",
            "validate_metric_column_references",
            "validate_normalization",
            "validate_null_policy",
            "validate_sampling",
            "validate_tolerance",
        ),
    },
    "recon_core.parser": {
        "compatibility_convenience_reexport": (
            "AMBIGUOUS_RESOURCE_FILE",
            "AuthoredContract",
            "AuthoredContractSummaryDict",
            "AuthoredEndpoint",
            "AuthoredEndpointDict",
            "ContractParseResult",
            "DUPLICATE_CONTRACT",
            "INVALID_CONTRACT",
            "INVALID_ENDPOINT",
            "INVALID_YAML",
            "LOCAL_RESOURCE_KIND_DEFINITIONS",
            "MANIFEST_ARTIFACT_TYPE",
            "MANIFEST_ARTIFACT_VERSION",
            "MISSING_REQUIRED_FIELD",
            "Manifest",
            "ManifestDict",
            "ManifestProject",
            "ManifestProjectDict",
            "ParsedProject",
            "RESOURCE_PATH_NOT_FOUND",
            "ResourceDiscoveryResult",
            "ResourceFile",
            "ResourceFileDict",
            "ResourceKindDefinition",
            "ResourceType",
            "SourceLocation",
            "SourceLocationDict",
            "UNKNOWN_FIELD",
            "YAML_FILE_READ_ERROR",
            "YamlLoadResult",
            "build_manifest",
            "discover_contract_files",
            "discover_resource_files",
            "load_parsed_project",
            "load_yaml_file",
            "load_yaml_text",
            "parse_contract_resource",
        ),
    },
    "recon_core.artifacts": {
        "compatibility_convenience_reexport": (
            "COMPILED_CHECKS_DIR_NAME",
            "COMPILED_CHECK_ARTIFACT_INVALID",
            "COMPILED_CHECK_ARTIFACT_NOT_FOUND",
            "COMPILED_CONTRACTS_DIR_NAME",
            "COMPILED_CONTRACT_ARTIFACT_INVALID",
            "COMPILED_CONTRACT_ARTIFACT_NOT_FOUND",
            "COMPILED_SQL_DIR_NAME",
            "CompiledCheckLoader",
            "CompiledCheckLoadResult",
            "CompiledCheckWriter",
            "CompiledContractLoader",
            "CompiledContractLoadResult",
            "CompiledContractWriter",
            "CompiledSqlWriteRequest",
            "CompiledSqlWriteResult",
            "CompiledSqlWriter",
            "LoadedCheckPlan",
            "LoadedCompiledCheck",
            "LoadedCompiledChecksArtifact",
            "LoadedCompiledContractArtifact",
            "LoadedCompiledEndpoint",
            "MANIFEST_FILE_NAME",
            "ManifestWriter",
            "NO_COMPILED_CHECKS",
        ),
    },
    "recon_core.profiles": {
        "compatibility_convenience_reexport": (
            "ConnectionConfig",
            "INVALID_PROFILE_CONFIG",
            "INVALID_PROFILE_YAML",
            "PROFILE_CONNECTION_NOT_FOUND",
            "PROFILE_ENV_VAR_MISSING",
            "PROFILE_FILE_NOT_FOUND",
            "PROFILE_NOT_FOUND",
            "PROFILE_NOT_SELECTED",
            "PROFILE_TARGET_NOT_FOUND",
            "ProfileLoadResult",
            "SelectedProfile",
            "load_selected_profile",
            "load_selected_profile_for_connection_names",
            "referenced_connection_names",
            "referenced_connection_names_from_compiled_contracts",
        ),
    },
    "recon_core.services": {
        "compatibility_convenience_reexport": (
            "CompileService",
            "ExitCategory",
            "InitService",
            "ParseService",
            "RunService",
            "ServiceResult",
            "exit_code_for",
        ),
    },
    "recon_core.config": {
        "compatibility_convenience_reexport": (
            "ConfiguredPath",
            "PathOrigin",
            "ProjectConfig",
            "ProjectConfigLoadResult",
            "load_project_config",
        ),
    },
    "recon_core.project": {
        "compatibility_convenience_reexport": (
            "PROJECT_FILE_NAME",
            "ProjectContext",
            "ProjectContextLoadResult",
            "ProjectPaths",
            "ResolvedResourcePath",
            "find_project_root",
            "load_project_context",
            "resolve_project_paths",
        ),
    },
    "recon_core.cli": {
        "compatibility_convenience_reexport": ("main",),
    },
}


@pytest.mark.regression_capture("python-package-import-surface-guard")
@pytest.mark.parametrize("module_name", sorted(PACKAGE_EXPORTS))
def test_package_exports_match_classified_import_surface(module_name: str) -> None:
    module = importlib.import_module(module_name)
    actual_names = tuple(module.__all__)
    classified_names = tuple(_classified_names(PACKAGE_EXPORTS[module_name].values()))

    assert len(actual_names) == len(set(actual_names))
    assert set(actual_names) == set(classified_names)
    for name in actual_names:
        assert hasattr(module, name)


def test_export_categories_are_known() -> None:
    categories = {
        category for module_categories in PACKAGE_EXPORTS.values() for category in module_categories
    }

    assert categories <= KNOWN_EXPORT_CATEGORIES


@pytest.mark.regression_capture("python-package-import-surface-guard")
def test_neutral_adapter_facade_excludes_concrete_and_internal_exports() -> None:
    adapters = importlib.import_module("recon_core.adapters")

    assert "DuckDbAdapter" not in adapters.__all__
    assert "DuckDbAdapterFactory" not in adapters.__all__
    assert "DuckDbSqlRenderer" not in adapters.__all__
    assert "default_runtime_renderers_by_adapter_type" not in adapters.__all__
    assert not hasattr(adapters, "DuckDbAdapter")
    assert not hasattr(adapters, "default_runtime_renderers_by_adapter_type")


@pytest.mark.regression_capture("python-package-import-surface-guard")
def test_neutral_adapter_facade_import_does_not_import_duckdb_modules() -> None:
    _run_isolated(
        """
        import sys
        import recon_core.adapters
        from recon_core.adapters import default_adapter_registry

        loaded = sorted(
            name for name in sys.modules if name.startswith("recon_core.adapters.duckdb")
        )
        if loaded:
            raise AssertionError(f"adapter facade imported DuckDB modules: {loaded}")
        if not callable(default_adapter_registry):
            raise AssertionError("default_adapter_registry is not callable")
        """
    )


@pytest.mark.regression_capture("python-package-import-surface-guard")
def test_default_adapter_registry_call_remains_available() -> None:
    from recon_core.adapters import AdapterRegistry, default_adapter_registry

    assert isinstance(default_adapter_registry(), AdapterRegistry)


@pytest.mark.regression_capture("python-package-import-surface-guard")
def test_concrete_duckdb_exports_remain_on_concrete_package() -> None:
    duckdb_package = importlib.import_module("recon_core.adapters.duckdb")

    assert {"DuckDbAdapter", "DuckDbAdapterFactory", "DuckDbSqlRenderer"} <= set(
        duckdb_package.__all__
    )
    assert hasattr(duckdb_package, "DuckDbAdapter")
    assert hasattr(duckdb_package, "DuckDbAdapterFactory")
    assert hasattr(duckdb_package, "DuckDbSqlRenderer")


def _classified_names(category_values: Iterable[tuple[str, ...]]) -> Iterable[str]:
    for names in category_values:
        yield from names


def _run_isolated(code: str) -> None:
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
        capture_output=True,
        text=True,
    )
