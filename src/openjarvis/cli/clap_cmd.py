"""``jarvis clap`` — listen for a double clap and open the OpenJarvis GUI."""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import webbrowser

import click
from rich.console import Console

_BACKEND_HOST = "127.0.0.1"
_BACKEND_PORT = 8000
_BACKEND_READY_TIMEOUT = 15.0
_FRONTEND_PORT = 5173


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _wait_for_backend(host: str, port: int, timeout: float) -> bool:
    """Poll until something accepts connections on host:port, or time out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.3)
    return False


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

    def _start_and_open_gui() -> None:
        # Already open from an earlier clap — just bring it back up in the
        # browser instead of spawning a second frontend on the same port
        # (which would fail with "port unavailable").
        if _port_open(_BACKEND_HOST, _FRONTEND_PORT):
            webbrowser.open(f"http://{_BACKEND_HOST}:{_FRONTEND_PORT}")
            return

        # Start the plain API server first (no-op if one is already running —
        # `start` just prints a warning and exits 1 in that case). Launching
        # the GUI with `--no-server` skips `jarvis gui`'s own server bootstrap,
        # which pulls in desktop extras that aren't installable on every
        # platform (e.g. onnxruntime has no macOS x86_64 wheel).
        subprocess.run([sys.executable, "-m", "openjarvis.cli", "start"], check=False)
        # Give the daemon a moment to actually bind before opening the browser —
        # otherwise the frontend loads with a "cannot reach backend" error.
        _wait_for_backend(_BACKEND_HOST, _BACKEND_PORT, _BACKEND_READY_TIMEOUT)
        subprocess.Popen(
            [sys.executable, "-m", "openjarvis.cli", "gui", "--no-server"]
        )

    def _open_gui() -> None:
        console.print("[green]Double clap detected — opening the GUI...[/green]")
        # Run off the audio thread: starting the server can take a few
        # seconds, and blocking here would stall the microphone stream.
        threading.Thread(target=_start_and_open_gui, daemon=True).start()

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
