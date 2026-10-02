"""macOS ``say`` TTS backend — local, offline, built into every Mac.

Exists mainly as a fallback for machines that can't run Kokoro (its PyTorch
dependency has no wheel for Intel Macs) and that don't have a cloud TTS API
key configured. Quality is lower than Kokoro, but it needs no install, no
API key, and no network.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

_SAMPLE_RATE = 22050
_DEFAULT_VOICE = "Luciana"  # pt-BR; built into macOS
_BASE_WORDS_PER_MINUTE = 180


@TTSRegistry.register("macos_say")
class MacSayBackend(TTSBackend):
    """Text-to-speech via the macOS ``say`` command-line tool."""

    backend_id = "macos_say"

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "wav",
    ) -> TTSResult:
        say = shutil.which("say")
        if say is None:
            raise RuntimeError("the macOS 'say' command is not available")

        rate = max(1, int(_BASE_WORDS_PER_MINUTE * speed))
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "speech.wav"
            subprocess.run(
                [
                    say,
                    "-v",
                    voice_id or _DEFAULT_VOICE,
                    "-r",
                    str(rate),
                    "--file-format=WAVE",
                    f"--data-format=LEI16@{_SAMPLE_RATE}",
                    "-o",
                    str(out_path),
                    text,
                ],
                check=True,
                capture_output=True,
            )
            audio = out_path.read_bytes()

        return TTSResult(
            audio=audio,
            format="wav",
            voice_id=voice_id or _DEFAULT_VOICE,
            sample_rate=_SAMPLE_RATE,
            metadata={"backend": "macos_say"},
        )

    def available_voices(self) -> List[str]:
        return ["Luciana", "Joana", "Samantha", "Daniel", "Alex"]

    def health(self) -> bool:
        return platform.system() == "Darwin" and shutil.which("say") is not None


__all__ = ["MacSayBackend"]
