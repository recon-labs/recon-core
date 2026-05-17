"""Click entry point for the Recon Core CLI."""

import click

from recon_core import get_version
from recon_core.services import (
    CompileService,
    ExitCategory,
    InitService,
    ParseService,
    RunService,
    ServiceResult,
    exit_code_for,
)

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _handle_result(result: ServiceResult) -> None:
    if result.exit_category is ExitCategory.SUCCESS:
        if result.message:
            click.echo(result.message)
        return

    _render_error(result)
    raise click.exceptions.Exit(exit_code_for(result.exit_category))


def _render_error(result: ServiceResult) -> None:
    message = result.message or "Command failed."
    click.echo(f"Error: {message}", err=True)
    for diagnostic in result.diagnostics:
        click.echo(f"Code: {diagnostic.code}", err=True)
        if diagnostic.path:
            click.echo(f"Path: {diagnostic.path}", err=True)
        if diagnostic.hint:
            click.echo(f"Hint: {diagnostic.hint}", err=True)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=get_version(), prog_name="recon")
def main() -> None:
    """Recon Core command-line interface."""


@main.command()
@click.argument("project_name")
def init(project_name: str) -> None:
    """Create a starter Recon project."""
    _handle_result(InitService(project_name=project_name).execute())


@main.command()
def parse() -> None:
    """Parse project files and write a manifest."""
    _handle_result(ParseService().execute())


@main.command(name="compile")
def compile_command() -> None:
    """Compile contracts into explicit execution artifacts."""
    _handle_result(CompileService().execute())


@main.command()
def run() -> None:
    """Run compiled reconciliation checks."""
    _handle_result(RunService().execute())
