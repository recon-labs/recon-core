"""Click entry point for the Recon Core CLI."""

import signal
from threading import Event, Thread, current_thread, main_thread
from types import FrameType

import click

from recon_core import get_version
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
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
        for diagnostic in result.diagnostics:
            if diagnostic.severity is DiagnosticSeverity.WARNING:
                _render_diagnostic(diagnostic)
        return

    _render_error(result)
    raise click.exceptions.Exit(exit_code_for(result.exit_category))


def _render_error(result: ServiceResult) -> None:
    message = result.message or "Command failed."
    click.echo(f"Error: {message}", err=True)
    for diagnostic in result.diagnostics:
        _render_diagnostic(diagnostic)


def _render_diagnostic(diagnostic: Diagnostic) -> None:
    click.echo(f"Code: {diagnostic.code}", err=True)
    label = "Warning" if diagnostic.severity is DiagnosticSeverity.WARNING else "Message"
    click.echo(f"{label}: {diagnostic.message}", err=True)
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
@click.option(
    "--render-sql",
    is_flag=True,
    help="Render adapter SQL for compiled checks.",
)
def compile_command(render_sql: bool) -> None:
    """Compile contracts into explicit execution artifacts."""
    _handle_result(CompileService(render_sql=render_sql).execute())


@main.command()
@click.option("--timeout-seconds", type=click.IntRange(min=1), help="Optional run deadline.")
def run(timeout_seconds: int | None) -> None:
    """Run compiled reconciliation checks."""
    _handle_result(_execute_cli_run(timeout_seconds))


def _execute_cli_run(timeout_seconds: int | None) -> ServiceResult:
    """Coordinate delivered SIGINT without interrupting cleanup or native ownership."""
    service = RunService()

    def execute_without_signal_control() -> ServiceResult:
        if timeout_seconds is None:
            return service.execute()
        return service.execute(timeout_seconds=timeout_seconds)

    if current_thread() is not main_thread():
        return execute_without_signal_control()
    previous = signal.getsignal(signal.SIGINT)
    if previous is None or previous == signal.SIG_IGN:
        return execute_without_signal_control()

    requested = False
    cancel_event = Event()
    finished = Event()
    results: list[ServiceResult] = []
    errors: list[BaseException] = []

    def request_stop(signum: int, frame: FrameType | None) -> None:
        nonlocal requested
        requested = True

    def execute() -> None:
        try:
            results.append(
                service.execute(timeout_seconds=timeout_seconds, cancel_event=cancel_event)
            )
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    try:
        signal.signal(signal.SIGINT, request_stop)
    except (OSError, ValueError):
        return execute_without_signal_control()

    worker = Thread(target=execute, name="recon-cli-run", daemon=False)
    try:
        worker.start()
        try:
            while not finished.is_set():
                if requested:
                    cancel_event.set()
                finished.wait(0.01)
        finally:
            if not finished.is_set():
                cancel_event.set()
            worker.join()
    finally:
        signal.signal(signal.SIGINT, previous)
    if errors:
        raise errors[0]
    return results[0]
