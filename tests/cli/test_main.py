import pytest
from click.testing import CliRunner

from recon_core import __version__
from recon_core.cli.main import main
from recon_core.services import CompileService, InitService, ParseService, RunService


def test_cli_version_outputs_package_version() -> None:
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_help_lists_core_commands() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    for command in ("init", "parse", "compile", "run"):
        assert command in result.output


@pytest.mark.parametrize("command", ["init", "parse", "compile", "run"])
def test_placeholder_commands_fail_clearly(command: str) -> None:
    result = CliRunner().invoke(main, [command])

    assert result.exit_code != 0
    assert f"recon {command} is not implemented yet." in result.output


@pytest.mark.parametrize(
    ("command", "service_cls"),
    [
        ("init", InitService),
        ("parse", ParseService),
        ("compile", CompileService),
        ("run", RunService),
    ],
)
def test_cli_commands_delegate_to_services(
    command: str,
    service_cls: type[InitService | ParseService | CompileService | RunService],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    original_execute = service_cls.execute

    def execute(self: InitService | ParseService | CompileService | RunService):
        nonlocal calls
        calls += 1
        return original_execute(self)

    monkeypatch.setattr(service_cls, "execute", execute)

    result = CliRunner().invoke(main, [command])

    assert result.exit_code != 0
    assert calls == 1
