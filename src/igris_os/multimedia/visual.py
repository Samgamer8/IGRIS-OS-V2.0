# -*- coding: utf-8 -*-
"""Verificacion visual automatica.

Detecta errores visuales reales en imagenes, video y capturas de interfaz:

- archivo no decodificable o sin dimensiones validas;
- fotograma/ventana en negro o en blanco (render fallido);
- imagen sin contraste (uniforme);
- bandas uniformes en los bordes (posible recorte o letterbox).

No finge "ver" texto recortado: para eso se usa la comparacion con una
referencia, que es exactamente lo que ``VisualCheck`` permite construir.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif",
                  ".tiff"}
VIDEO_SUFFIXES = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}

BLANK_DARK = 8
BLANK_LIGHT = 247
BLANK_RATIO_LIMIT = 0.995
MIN_CONTRAST = 2.0


@dataclass(frozen=True, slots=True)
class VisualCheck:
    ok: bool
    message: str
    path: str = ""
    width: int = 0
    height: int = 0
    mean_brightness: float = 0.0
    std_brightness: float = 0.0
    blank_ratio: float = 0.0
    blank: bool = False
    uniform_borders: tuple[str, ...] = ()
    duration: float = 0.0
    codec: str = ""


@dataclass(frozen=True, slots=True)
class ReferenceComparison:
    ok: bool
    message: str
    image: str = ""
    reference: str = ""
    similarity: float = 0.0
    mae: float = 0.0
    changed_ratio: float = 0.0
    diff_bbox: tuple[int, int, int, int] | None = None


class VisualVerifier:
    """Comprueba que una imagen/video/captura es realmente visible."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")

    # ------------------------------------------------------------------
    # Imagenes
    # ------------------------------------------------------------------
    def verify_image(self, path: Path | str) -> VisualCheck:
        target = Path(path)
        try:
            from PIL import Image, ImageStat
        except ImportError:
            return VisualCheck(False, "Pillow no esta instalado", str(target))
        if not target.is_file() or target.is_symlink():
            return VisualCheck(False, "Imagen no disponible", str(target))
        try:
            with Image.open(target) as image:
                image.load()
                gray = image.convert("L")
                width, height = gray.size
                if width < 2 or height < 2:
                    return VisualCheck(
                        False, "Dimensiones invalidas", str(target),
                        width, height)
                stat = ImageStat.Stat(gray)
                mean = float(stat.mean[0])
                std = float(stat.stddev[0])
                histogram = gray.histogram()
                total = width * height
                dark = sum(histogram[:BLANK_DARK])
                light = sum(histogram[BLANK_LIGHT + 1:])
                blank_ratio = (dark + light) / total
                blank = blank_ratio >= BLANK_RATIO_LIMIT
                borders = self._uniform_borders(gray)
        except (OSError, ValueError) as exc:
            return VisualCheck(False, f"Imagen no decodificable: {exc}",
                               str(target))

        if blank:
            return VisualCheck(
                False, "Fotograma en negro o en blanco (render fallido)",
                str(target), width, height, mean, std, blank_ratio, True,
                borders)
        if std < MIN_CONTRAST:
            return VisualCheck(
                False, "Imagen sin contraste (contenido uniforme)",
                str(target), width, height, mean, std, blank_ratio, False,
                borders)
        message = "Imagen verificada"
        if borders:
            message += " · bordes uniformes: " + ", ".join(borders)
        return VisualCheck(
            True, message, str(target), width, height, mean, std, blank_ratio,
            False, borders)

    @staticmethod
    def _uniform_borders(gray) -> tuple[str, ...]:
        """Detecta bandas de un solo color pegadas a los bordes (posible
        recorte o letterbox)."""
        width, height = gray.size
        band = max(4, min(width, height) // 25)
        if width < band * 2 or height < band * 2:
            return ()
        px = gray.load()
        borders = []
        top_color = px[0, 0]
        if all(px[x, y] == top_color for x in range(width) for y in range(band)):
            borders.append("top")
        bottom_color = px[0, height - 1]
        if all(px[x, height - 1 - y] == bottom_color
               for x in range(width) for y in range(band)):
            borders.append("bottom")
        left_color = px[0, 0]
        if all(px[x, y] == left_color for y in range(height) for x in range(band)):
            borders.append("left")
        right_color = px[width - 1, 0]
        if all(px[width - 1 - x, y] == right_color
               for y in range(height) for x in range(band)):
            borders.append("right")
        return tuple(borders)

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------
    def verify_video(self, path: Path | str) -> VisualCheck:
        target = Path(path)
        if not self.ffprobe or not self.ffmpeg:
            return VisualCheck(False, "FFmpeg no esta disponible", str(target))
        if not target.is_file() or target.is_symlink():
            return VisualCheck(False, "Video no disponible", str(target))
        probe = self._probe(target)
        if not probe:
            return VisualCheck(False, "Video no decodificable", str(target))
        video_streams = [s for s in probe.get("streams", ())
                         if s.get("codec_type") == "video"]
        if not video_streams:
            return VisualCheck(False, "Sin flujo de video", str(target))
        stream = video_streams[0]
        codec = str(stream.get("codec_name", ""))
        duration = float(probe.get("format", {}).get("duration", 0.0) or 0.0)

        frame_dir = Path(tempfile.mkdtemp(prefix="igris_verify_"))
        frame = frame_dir / "frame.png"
        command = [self.ffmpeg, "-y", "-ss", "0", "-i", str(target.resolve()),
                   "-frames:v", "1", str(frame)]
        try:
            run = subprocess.run(command, capture_output=True, text=True,
                                 timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return VisualCheck(False, "Extraccion de fotograma agoto el tiempo",
                               str(target), duration=duration, codec=codec)
        if run.returncode != 0 or not frame.is_file():
            return VisualCheck(False, "No se pudo extraer un fotograma",
                               str(target), duration=duration, codec=codec)
        check = self.verify_image(frame)
        return VisualCheck(
            check.ok, check.message, str(target), check.width, check.height,
            check.mean_brightness, check.std_brightness, check.blank_ratio,
            check.blank, check.uniform_borders, duration, codec)

    def _probe(self, path: Path) -> dict:
        import json
        try:
            run = subprocess.run(
                [self.ffprobe, "-v", "error", "-show_format", "-show_streams",
                 "-of", "json", str(path.resolve())],
                capture_output=True, text=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            return {}
        if run.returncode != 0:
            return {}
        try:
            return json.loads(run.stdout)
        except ValueError:
            return {}

    # ------------------------------------------------------------------
    # Despacho y captura de interfaz
    # ------------------------------------------------------------------
    def verify(self, path: Path | str) -> VisualCheck:
        suffix = Path(path).suffix.casefold()
        if suffix in VIDEO_SUFFIXES:
            return self.verify_video(path)
        return self.verify_image(path)

    def capture_widget(self, widget, output: Path | str | None = None) -> VisualCheck:
        """Captura un widget PyQt y verifica que no esta en negro/roto."""
        target = Path(output) if output else (
            Path(tempfile.mkdtemp(prefix="igris_capture_")) / "captura.png")
        try:
            grabbed = widget.grab().toImage()
        except Exception as exc:
            return VisualCheck(False, f"No se pudo capturar la interfaz: {exc}",
                               str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        if not grabbed.save(str(target), "PNG"):
            return VisualCheck(False, "No se pudo guardar la captura",
                               str(target))
        return self.verify_image(target)

    # ------------------------------------------------------------------
    # Comparacion con referencia (regresion visual)
    # ------------------------------------------------------------------
    def compare_reference(self, image: Path | str, reference: Path | str, *,
                          similarity_min: float = 0.85,
                          changed_area_max: float = 0.15) -> ReferenceComparison:
        """Compara una captura con una imagen de referencia.

        Devuelve similitud, area cambiada y la caja de la region mas distinta,
        para poder detectar "elementos recortados o desplazados" de forma medible.
        """
        try:
            import numpy as np
        except ImportError:
            return ReferenceComparison(False, "numpy no esta disponible")
        try:
            from PIL import Image
        except ImportError:
            return ReferenceComparison(False, "Pillow no esta disponible")
        image_path = Path(image)
        ref_path = Path(reference)
        for label, path in (("imagen", image_path), ("referencia", ref_path)):
            if not path.is_file() or path.is_symlink():
                return ReferenceComparison(
                    False, f"{label} no disponible", str(image_path),
                    str(ref_path))
        try:
            with Image.open(image_path) as im, Image.open(ref_path) as rf:
                im.load()
                rf.load()
                size = (min(im.width, rf.width), min(im.height, rf.height))
                gray_a = np.asarray(im.convert("L").resize(size),
                                    dtype=np.float64)
                gray_b = np.asarray(rf.convert("L").resize(size),
                                    dtype=np.float64)
        except (OSError, ValueError) as exc:
            return ReferenceComparison(
                False, f"Imagen no decodificable: {exc}", str(image_path),
                str(ref_path))

        difference = np.abs(gray_a - gray_b)
        mae = float(difference.mean())
        similarity = float(max(0.0, 1.0 - mae / 255.0))
        changed = difference > 32.0
        changed_ratio = float(changed.mean())
        diff_bbox = None
        if bool(changed.any()):
            rows = np.any(changed, axis=1)
            cols = np.any(changed, axis=0)
            y0 = int(np.argmax(rows))
            y1 = int(rows.size - np.argmax(rows[::-1]))
            x0 = int(np.argmax(cols))
            x1 = int(cols.size - np.argmax(cols[::-1]))
            diff_bbox = (x0, y0, x1, y1)
        ok = similarity >= similarity_min and changed_ratio <= changed_area_max
        if ok:
            message = f"Coincide con la referencia (similitud {similarity:.2f})"
        else:
            message = (
                f"Difiere de la referencia: similitud {similarity:.2f} "
                f"(min {similarity_min:.2f}), area cambiada {changed_ratio:.1%} "
                f"(max {changed_area_max:.1%})")
        return ReferenceComparison(ok, message, str(image_path), str(ref_path),
                                   similarity, mae, changed_ratio, diff_bbox)
