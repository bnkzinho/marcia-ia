"""Listens on the default microphone and fires a callback on a double clap.

A clap is detected as a sharp rise in RMS amplitude (an "onset") followed by
a quick decay — unlike speech, which stays loud over many consecutive
chunks. Two onsets close enough together (but not too close — that's just
the echo/tail of a single clap) count as a double clap.
"""

from __future__ import annotations

import struct
import time
from collections.abc import Callable
from dataclasses import dataclass

_SAMPLE_RATE = 16000
_CHUNK = 512  # ~32ms per chunk at 16kHz — fine enough to catch a clap's onset

# Gap between the two onsets of a deliberate double clap. Too close together
# (< MIN) is almost certainly the same clap's echo/tail, not a second clap.
# Too far apart (> MAX) is two unrelated sounds, not a deliberate gesture.
_MIN_CLAP_GAP = 0.08
_MAX_CLAP_GAP = 1.0
# Minimum time between counted onsets, regardless of the double-clap logic —
# prevents one loud transient's decay from registering as several onsets.
_ONSET_REFRACTORY = 0.12
# After a successful trigger, ignore everything for this long so the sound
# of the triggered action itself (e.g. a browser opening) can't re-trigger it.
_TRIGGER_COOLDOWN = 2.5


def _rms(data: bytes) -> float:
    """RMS amplitude of 16-bit PCM bytes."""
    n = len(data) // 2
    if n == 0:
        return 0.0
    shorts = struct.unpack(f"{n}h", data[: n * 2])
    return (sum(s * s for s in shorts) / n) ** 0.5


@dataclass
class ClapTriggerConfig:
    threshold: float = 1800.0
    """RMS level a chunk must cross (from below) to count as a clap onset.
    Run with --calibrate to see live levels on your own mic before picking
    a value — rooms and microphones vary a lot."""
    sample_rate: int = _SAMPLE_RATE
    chunk: int = _CHUNK
    min_gap: float = _MIN_CLAP_GAP
    max_gap: float = _MAX_CLAP_GAP
    onset_refractory: float = _ONSET_REFRACTORY
    trigger_cooldown: float = _TRIGGER_COOLDOWN


def listen_for_double_clap(
    on_double_clap: Callable[[], None],
    *,
    config: ClapTriggerConfig | None = None,
    on_level: Callable[[float, bool], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> None:
    """Block the current thread, listening for double claps.

    ``on_double_clap`` runs every time two claps land within the configured
    gap. ``on_level`` (optional) runs on every chunk with ``(rms, is_onset)``
    — wire it up to print live levels for calibration. ``should_stop``
    (optional) is polled between chunks so callers can request a clean exit.

    Raises RuntimeError if sounddevice is not installed.
    """
    try:
        import sounddevice as sd
    except ImportError:
        raise RuntimeError(
            "sounddevice is required for the clap trigger. "
            "Install with: pip install sounddevice"
        )

    cfg = config or ClapTriggerConfig()

    last_onset_at: float | None = None
    pending_onset_at: float | None = None
    last_trigger_at: float = 0.0
    was_above_threshold = False

    with sd.RawInputStream(
        samplerate=cfg.sample_rate,
        channels=1,
        dtype="int16",
        blocksize=cfg.chunk,
    ) as stream:
        while should_stop is None or not should_stop():
            raw, _ = stream.read(cfg.chunk)
            amplitude = _rms(bytes(raw))
            now = time.monotonic()

            is_rising_onset = amplitude > cfg.threshold and not was_above_threshold
            was_above_threshold = amplitude > cfg.threshold

            if on_level is not None:
                on_level(amplitude, is_rising_onset)

            if not is_rising_onset:
                continue
            if now - last_trigger_at < cfg.trigger_cooldown:
                continue
            if last_onset_at is not None and now - last_onset_at < cfg.onset_refractory:
                continue

            last_onset_at = now

            if pending_onset_at is None:
                # First clap of a potential pair — wait to see if a second
                # one lands in the window.
                pending_onset_at = now
                continue

            gap = now - pending_onset_at
            if cfg.min_gap <= gap <= cfg.max_gap:
                pending_onset_at = None
                last_trigger_at = now
                on_double_clap()
            else:
                # Too close or too far to be the second clap of a pair —
                # treat this onset as the new first clap instead.
                pending_onset_at = now


__all__ = ["ClapTriggerConfig", "listen_for_double_clap"]
