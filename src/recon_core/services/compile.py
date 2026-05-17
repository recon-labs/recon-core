"""Compile command service."""

from recon_core.services._not_implemented import not_implemented_result
from recon_core.services.results import ServiceResult


class CompileService:
    """Service boundary for recon compile."""

    def execute(self) -> ServiceResult:
        return not_implemented_result("compile", self.__class__.__name__)
