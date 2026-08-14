import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class VoiceSample:
    index: int
    text: str
    audio: str
    seconds: float
    valid: bool


PILOT_SCRIPT = (
    "IGRIS OS en línea. A tus órdenes.",
    "Analizaré la misión antes de ejecutar cualquier cambio.",
    "El sistema permanece estable y todos los módulos responden.",
    "He localizado tres archivos que requieren verificación.",
    "La operación ha terminado correctamente.",
    "No ejecutaré esa acción sin una confirmación explícita.",
    "Preparando el entorno de desarrollo y las pruebas automáticas.",
    "La seguridad y la integridad de los datos son prioritarias.",
    "Voy a construir una solución directa, eficiente y verificable.",
    "El repositorio ha sido analizado sin modificar los archivos originales.",
    "Comprobando imagen, sonido, vídeo y memoria técnica.",
    "La misión está en progreso. Mantendré informado al usuario.",
    "Se ha detectado un error. Aplicaré una reparación controlada.",
    "Todas las pruebas han sido superadas.",
    "IGRIS está preparado para recibir una nueva orden.",
)


class VoiceDatasetRecorder:
    def __init__(self, root: Path, device: str,
                 ffmpeg: str = "ffmpeg", ffprobe: str = "ffprobe") -> None:
        self.root = root.resolve()
        self.device = device
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe

    def record(self, index: int, text: str, seconds: int = 10) -> VoiceSample:
        if not text.strip() or not 2 <= seconds <= 30:
            raise ValueError("Muestra invalida")
        audio = self.root / "audio" / f"{index:04d}.wav"
        audio.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "dshow", "-i", f"audio={self.device}", "-t", str(seconds),
            "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(audio),
        ]
        run = subprocess.run(command, capture_output=True, text=True,
                             timeout=seconds + 15)
        if run.returncode != 0:
            raise RuntimeError(run.stderr[-1000:] or "Fallo de grabacion")
        duration = self._duration(audio)
        return VoiceSample(index, text, str(audio), duration, duration >= 1.0)

    def save_manifest(self, samples: list[VoiceSample]) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / "manifest.json"
        document = {
            "speaker_consent": True,
            "speaker": "usuario_propietario",
            "purpose": "voz original autorizada para IGRIS OS",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "format": {"sample_rate": 24000, "channels": 1, "codec": "pcm_s16le"},
            "samples": [asdict(sample) for sample in samples],
        }
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
        return target

    def _duration(self, audio: Path) -> float:
        run = subprocess.run([
            self.ffprobe, "-v", "error", "-show_entries",
            "format=duration", "-of", "default=nw=1:nk=1", str(audio),
        ], capture_output=True, text=True, timeout=10)
        try:
            return float(run.stdout.strip()) if run.returncode == 0 else 0.0
        except ValueError:
            return 0.0
