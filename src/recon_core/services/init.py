"""Init command service."""

from recon_core.services._not_implemented import not_implemented_result
from recon_core.services.results import ServiceResult


class InitService:
    """Service boundary for recon init."""

    def execute(self) -> ServiceResult:
        return not_implemented_result("init", self.__class__.__name__)
