"""Private boundary between admitted checks and check-scoped native reads."""

from collections.abc import Callable
from typing import Protocol

from recon_core.adapters._aggregate_runtime import _AggregateQueryExecutor
from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.models import QueryResult, Relation
from recon_core.artifacts import LoadedCompiledCheck, LoadedCompiledContractArtifact
from recon_core.check_engine.models import CheckResult


class _BoundReader(_AggregateQueryExecutor, Protocol):
    def execute(self, query: str) -> QueryResult: ...


_BoundEvaluation = Callable[[Relation, Relation, _BoundReader], CheckResult]


class _BoundRunner(Protocol):
    def run(
        self,
        check: LoadedCompiledCheck,
        contract: LoadedCompiledContractArtifact,
        adapter: BaseAdapter,
        evaluate: _BoundEvaluation,
    ) -> CheckResult: ...
