"""Version helpers for Recon Core."""

from importlib.metadata import PackageNotFoundError, version

PACKAGE_NAME = "recon-core"
FALLBACK_VERSION = "0.0.0"


def get_version() -> str:
    """Return the installed package version, falling back for source-tree imports."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return FALLBACK_VERSION


__version__ = get_version()
