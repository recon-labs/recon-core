"""Run command service."""

from recon_core.services._not_implemented import not_implemented_result
from recon_core.services.results import ServiceResult


class RunService:
    """Service boundary for recon run."""

    def execute(self) -> ServiceResult:
        return not_implemented_result("run", self.__class__.__name__)
