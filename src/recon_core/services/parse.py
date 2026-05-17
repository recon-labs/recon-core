"""Parse command service."""

from recon_core.services._not_implemented import not_implemented_result
from recon_core.services.results import ServiceResult


class ParseService:
    """Service boundary for recon parse."""

    def execute(self) -> ServiceResult:
        return not_implemented_result("parse", self.__class__.__name__)
