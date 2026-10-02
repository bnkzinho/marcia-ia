"""``jarvis clap`` — listen for a double clap and open the OpenJarvis GUI."""

from __future__ import annotations

import subprocess
import sys

import click
from rich.console import Console


@click.command()
@click.option(
    "--threshold",
    default=1800.0,
    show_default=True,
    type=float,
    help="RMS level a clap must cross to be detected. Tune with --calibrate.",
)
@click.option(
    "--min-gap",
    default=0.08,
    show_default=True,
    type=float,
    help="Minimum seconds between the two claps of a double clap.",
)
@click.option(
    "--max-gap",
    default=1.0,
    show_default=True,
    type=float,
    help="Maximum seconds between the two claps of a double clap.",
)
@click.option(
    "--calibrate",
    is_flag=True,
    help="Print live microphone levels instead of launching anything — use this "
    "to pick a --threshold value for your room and microphone.",
)
def clap(threshold: float, min_gap: float, max_gap: float, calibrate: bool) -> None:
    """Listen on the microphone and open the OpenJarvis GUI on a double clap.

    Runs until interrupted with Ctrl+C. Each detected double clap launches
    ``jarvis gui`` in the background, so this listener keeps running and can
    fire again later.
    """
    from openjarvis.speech.clap_trigger import ClapTriggerConfig, listen_for_double_clap

    console = Console(stderr=True)
    config = ClapTriggerConfig(threshold=threshold, min_gap=min_gap, max_gap=max_gap)

    if calibrate:
        console.print(
            "[cyan]Calibrating — clap, talk, make room noise. "
            "Ctrl+C to stop.[/cyan]"
        )
        console.print(f"[cyan]Current threshold: {threshold}[/cyan]")

        def _on_level(rms: float, is_onset: bool) -> None:
            marker = " <- onset" if is_onset else ""
            console.print(f"level: {rms:8.1f}{marker}")

        try:
            listen_for_double_clap(
                lambda: None, config=config, on_level=_on_level
            )
        except KeyboardInterrupt:
            pass
        return

    def _open_gui() -> None:
        console.print("[green]Double clap detected — opening the GUI...[/green]")
        subprocess.Popen([sys.executable, "-m", "openjarvis.cli", "gui"])

    console.print(
        f"[cyan]Listening for a double clap (threshold={threshold})... "
        "Ctrl+C to stop.[/cyan]"
    )
    try:
        listen_for_double_clap(_open_gui, config=config)
    except KeyboardInterrupt:
        console.print("[cyan]Stopped.[/cyan]")
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


__all__ = ["clap"]
