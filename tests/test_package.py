import recon_core


def test_package_imports() -> None:
    assert recon_core.__version__ == "0.0.0"


def test_get_version_returns_string() -> None:
    assert isinstance(recon_core.get_version(), str)
