"""Click entry point for the Recon Core CLI."""

import click

from recon_core import get_version

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _not_implemented(command_name: str) -> None:
    raise click.ClickException(f"recon {command_name} is not implemented yet.")


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=get_version(), prog_name="recon")
def main() -> None:
    """Recon Core command-line interface."""


@main.command()
def init() -> None:
    """Create a starter Recon project."""
    _not_implemented("init")


@main.command()
def parse() -> None:
    """Parse project files and write a manifest."""
    _not_implemented("parse")


@main.command(name="compile")
def compile_command() -> None:
    """Compile contracts into explicit execution artifacts."""
    _not_implemented("compile")


@main.command()
def run() -> None:
    """Run compiled reconciliation checks."""
    _not_implemented("run")
