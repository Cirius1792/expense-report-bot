"""Behave steps that assert on the CLI's own stdout (E12 anti-spill, Task 11).

The CLI scenarios run the production entry point in-process, so the user-visible
artefact is what that run prints. Behave captures each scenario's stdout/stderr/
log (``context.captured``); these steps read that snapshot — no monkey-patching.
"""

from __future__ import annotations

from typing import Any

from behave import then


def _cli_stdout(context: Any) -> str:
    """The stdout this scenario printed so far, as captured by behave."""
    captured = getattr(context, "captured", None)
    stdout = getattr(captured, "stdout", None)
    assert stdout is not None, "behave output capture must be enabled for CLI steps"
    return stdout


@then('the CLI should have printed "{line}"')
def step_cli_printed_line(context: Any, line: str) -> None:
    """True when that exact line was printed by the CLI."""
    printed = _cli_stdout(context).splitlines()
    assert line in printed, f'Expected "{line}" among printed lines, got: {printed}'


@then('the CLI output should not contain "{text}"')
def step_cli_output_omits(context: Any, text: str) -> None:
    """True when that text appears nowhere in the CLI's stdout."""
    stdout = _cli_stdout(context)
    assert stdout, "Expected non-empty CLI stdout to assert against"
    assert text not in stdout, f'Expected "{text}" absent from CLI stdout, got: {stdout}'
