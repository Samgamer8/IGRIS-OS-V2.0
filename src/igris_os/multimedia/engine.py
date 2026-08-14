import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from igris_os.tools import safe_output


@dataclass(frozen=True, slots=True)
class MediaResult:
    ok: bool
    message: str
    output: str = ""


class MediaEngine:
    def __init__(self, workspace: Path, timeout: int = 300) -> None:
        self.workspace = workspace.resolve()
        self.timeout = timeout
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)

    def probe(self, source: Path) -> dict:
        if not self.ffprobe or not source.is_file():
            return {}
        run = subprocess.run(
            [self.ffprobe, "-v", "error", "-show_format", "-show_streams",
             "-of", "json", str(source.resolve())],
            capture_output=True, text=True, timeout=30)
        return json.loads(run.stdout) if run.returncode == 0 else {}

    def transcode(self, source: Path, output: str, *,
                  video_codec: str = "libx264", audio_codec: str = "aac",
                  confirmed: bool = False) -> MediaResult:
        if not confirmed:
            return MediaResult(False, "Se necesita confirmacion")
        if not self.ffmpeg or not source.is_file():
            return MediaResult(False, "FFmpeg o archivo no disponible")
        target = safe_output(self.workspace, output)
        command = [self.ffmpeg, "-y", "-i", str(source.resolve()),
                   "-c:v", video_codec, "-c:a", audio_codec, str(target)]
        return self._run(command, target)

    def extract_audio(self, source: Path, output: str,
                      *, confirmed: bool = False) -> MediaResult:
        if not confirmed:
            return MediaResult(False, "Se necesita confirmacion")
        if not self.ffmpeg or not source.is_file():
            return MediaResult(False, "FFmpeg o archivo no disponible")
        target = safe_output(self.workspace, output)
        return self._run([self.ffmpeg, "-y", "-i", str(source.resolve()),
                          "-vn", "-c:a", "libmp3lame", str(target)], target)

    def thumbnail(self, source: Path, output: str, second: float = 0,
                  *, confirmed: bool = False) -> MediaResult:
        if not confirmed:
            return MediaResult(False, "Se necesita confirmacion")
        if not self.ffmpeg or not source.is_file():
            return MediaResult(False, "FFmpeg o archivo no disponible")
        target = safe_output(self.workspace, output)
        return self._run([self.ffmpeg, "-y", "-ss", str(max(0, second)),
                          "-i", str(source.resolve()), "-frames:v", "1",
                          str(target)], target)

    def trim(self, source: Path, output: str, start: float, duration: float,
             *, confirmed: bool = False) -> MediaResult:
        if not confirmed:
            return MediaResult(False, "Se necesita confirmacion")
        if start < 0 or duration <= 0 or duration > 86_400:
            return MediaResult(False, "Intervalo multimedia invalido")
        if not self.ffmpeg or not source.is_file():
            return MediaResult(False, "FFmpeg o archivo no disponible")
        target = safe_output(self.workspace, output)
        return self._run([
            self.ffmpeg, "-y", "-ss", str(start), "-i", str(source.resolve()),
            "-t", str(duration), "-c:v", "libx264", "-c:a", "aac",
            str(target)], target)

    def _run(self, command: list[str], target: Path) -> MediaResult:
        try:
            run = subprocess.run(command, capture_output=True, text=True,
                                 timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return MediaResult(False, "FFmpeg agoto el tiempo")
        if run.returncode or not target.exists():
            return MediaResult(False, (run.stderr or "FFmpeg fallo")[-1500:])
        return MediaResult(True, "Operacion multimedia completada", str(target))
