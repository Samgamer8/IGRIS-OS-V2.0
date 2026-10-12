"""Analisis estatico de artefactos (binarios y empaquetados) sin codigo fuente.

Veracidad: igual que la busqueda en GitHub, esto NO lo inventa el LLM. Lee los
bytes reales del archivo (magic bytes, cabecera PE, strings, contenido ZIP) y
devuelve hechos con la evidencia que los respalda. Todo es local y de solo
lectura, pensado para software propio o autorizado (investigacion,
interoperabilidad, preservacion). No eluye protecciones ni licencias.

Limite honesto: con la stdlib de Python NO se desensambla ni decompila. Para
eso hacen falta capstone/Ghidra/IDA/Hopper, que no estan instalados. Cuando no
se puede concluir algo con certeza, se declara en ``limitations`` en lugar de
inventarlo.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import struct
import zipfile
from datetime import datetime, timezone
from pathlib import Path


# Firmas (magic bytes) de los formatos que sabemos reconocer.
_MAGIC_SIGNATURES = (
    (b"MZ", "pe", "Ejecutable o libreria de Windows (formato PE)"),
    (b"\x7fELF", "elf", "Binario ELF (Linux/Unix)"),
    (b"PK\x03\x04", "zip", "Archivo ZIP (posible JAR/APK/DOCX/instalador)"),
    (b"\xfe\xed\xfa\xce", "mach-o", "Binario Mach-O 32-bit (macOS)"),
    (b"\xfe\xed\xfa\xcf", "mach-o", "Binario Mach-O 64-bit (macOS)"),
    (b"\xce\xfa\xed\xfe", "mach-o", "Binario Mach-O 32-bit little-endian (macOS)"),
    (b"\xcf\xfa\xed\xfe", "mach-o", "Binario Mach-O 64-bit little-endian (macOS)"),
    (b"\xca\xfe\xba\xbe", "java-class", "Clase Java compilada / Mach-O universal"),
    (b"dex\n", "dex", "Dalvik Executable (codigo Android)"),
)

# Maquina objetivo en la cabecera COFF de un PE.
_PE_MACHINES = {
    0x014C: "x86 (32-bit)",
    0x8664: "x64 (AMD64)",
    0x01C0: "ARM",
    0x01C4: "ARMNT",
    0xAA64: "ARM64",
    0x0200: "IA64 (Itanium)",
}

# Firmas de empaquetado / framework. Solo las especificas: evita falsos positivos.
_PACKERS = (
    (b"pyi-", "PyInstaller"),
    (b"_MEIPASS", "PyInstaller"),
    (b"pyimod", "PyInstaller"),
    (b"pyiboot", "PyInstaller"),
    (b"Nuitka", "Nuitka"),
    (b"__compiled__", "Nuitka"),
    (b"cx_Freeze", "cx_Freeze"),
    (b"py2exe", "py2exe"),
    (b"app.asar", "Electron (Node.js)"),
    (b"UPX!", "UPX (compresor de ejecutables)"),
    (b"NullsoftInst", "Nullsoft Scriptable Install System (NSIS)"),
    (b"Inno Setup", "Inno Setup"),
    (b"jrsoftware", "Inno Setup"),
    (b"Go build ID", "Go (binario compilado en Go)"),
    (b"rustc", "Rust (binario compilado en Rust)"),
)

_URL_RE = re.compile(rb"https?://[^\s\"'<>)\]\\\x00-\x08\x0b\x0c\x0e-\x1f]{4,200}", re.IGNORECASE)
_ASCII_RE = re.compile(rb"[\x20-\x7e]{5,}")


@dataclass(frozen=True, slots=True)
class ArtifactReport:
    """Informe de analisis de un artefacto, con evidencia y limites declarados."""

    path: str
    size: int
    sha256: str
    kind: str
    kind_description: str
    architecture: str = ""
    bitness: str = ""
    timestamp: str = ""
    sections: int = 0
    is_dotnet: bool = False
    packer: str = ""
    framework: str = ""
    urls: tuple[str, ...] = ()
    notable_strings: tuple[str, ...] = ()
    zip_entries: tuple[dict, ...] = ()
    notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    error: str = ""

class ArtifactAnalyzer:
    """Inspecciona un binario o artefacto empaquetado sin su codigo fuente."""

    def __init__(self, *, max_sample_bytes: int = 32 * 1024 * 1024) -> None:
        self.max_sample_bytes = max_sample_bytes

    def analyze(self, path: str | Path) -> ArtifactReport:
        target = Path(path)
        if not target.is_file() or target.is_symlink():
            raise ValueError("La ruta no es un archivo regular: " + str(path))
        size = target.stat().st_size
        sha256 = self._digest(target)

        # Cabecera (los magic bytes y la PE viven en los primeros KB).
        with target.open("rb") as stream:
            head = stream.read(65536)
            stream.seek(0)
            sample = stream.read(self.max_sample_bytes)

        kind, kind_description = self._detect_kind(head)
        limitations: list[str] = [
            "Sin desensamblado ni decompilacion: requiere capstone/Ghidra/IDA/Hopper "
            "(no instalados). Este analisis es estatico y de solo lectura.",
        ]
        notes: list[str] = []
        architecture = bitness = timestamp = ""
        sections = 0
        is_dotnet = False

        if kind == "pe":
            pe = self._parse_pe(head)
            architecture = pe["architecture"]
            bitness = pe["bitness"]
            timestamp = pe["timestamp"] or ""
            sections = pe["sections"]
            is_dotnet = pe["is_dotnet"]
            notes.extend(pe["evidence"])

        packer, packer_evidence = self._detect_packer(sample)
        notes.extend(packer_evidence)

        framework = ""
        zip_entries: tuple[dict, ...] = ()
        if kind == "zip":
            zip_entries, zip_info = self._inspect_zip(target)
            framework = zip_info["framework"]
            notes.extend(zip_info["notes"])

        urls = self._extract_urls(sample)
        notable = self._notable_strings(sample, urls)
        if size > self.max_sample_bytes:
            limitations.append(
                f"Strings y URLs limitados a los primeros "
                f"{self.max_sample_bytes // (1024 * 1024)} MB del archivo."
            )

        return ArtifactReport(
            path=str(target), size=size, sha256=sha256, kind=kind,
            kind_description=kind_description, architecture=architecture,
            bitness=bitness, timestamp=timestamp, sections=sections,
            is_dotnet=is_dotnet, packer=packer, framework=framework,
            urls=urls, notable_strings=notable, zip_entries=zip_entries,
            notes=tuple(notes), limitations=tuple(limitations),
        )

    @staticmethod
    def _digest(target: Path) -> str:
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _detect_kind(head: bytes) -> tuple[str, str]:
        for signature, kind, description in _MAGIC_SIGNATURES:
            if head.startswith(signature):
                return kind, description
        if head[:2] == b"#!":
            return "script", "Script con shebang"
        window = head[:512]
        if window:
            printable = sum(1 for b in window if 9 <= b <= 13 or 32 <= b <= 126)
            if printable / len(window) > 0.9:
                return "text", "Archivo de texto"
        return "unknown", "Formato no reconocido por las firmas conocidas"

    @staticmethod
    def _parse_pe(head: bytes) -> dict:
        result = {"architecture": "", "bitness": "", "timestamp": "",
                  "sections": 0, "is_dotnet": False, "evidence": []}
        if len(head) < 0x40:
            result["evidence"].append("Cabecera demasiado corta para PE")
            return result
        try:
            e_lfanew = struct.unpack_from("<I", head, 0x3C)[0]
        except struct.error:
            result["evidence"].append("No se pudo leer e_lfanew")
            return result
        if head[e_lfanew:e_lfanew + 4] != b"PE\x00\x00":
            result["evidence"].append("Firma 'PE\\0\\0' no encontrada en e_lfanew")
            return result
        coff = e_lfanew + 4
        try:
            machine, num_sections, timestamp_raw = struct.unpack_from("<HHI", head, coff)
        except struct.error:
            result["evidence"].append("Cabecera COFF incompleta")
            return result
        result["architecture"] = _PE_MACHINES.get(
            machine, f"desconocida (0x{machine:04x})")
        result["sections"] = num_sections
        if timestamp_raw:
            try:
                result["timestamp"] = datetime.fromtimestamp(
                    timestamp_raw, tz=timezone.utc).isoformat()
            except (OSError, OverflowError, ValueError):
                result["timestamp"] = ""
        result["evidence"].append(
            f"Machine=0x{machine:04x}, secciones={num_sections}")
        optional = coff + 20
        opt_magic = None
        if len(head) >= optional + 2:
            opt_magic = struct.unpack_from("<H", head, optional)[0]
        if opt_magic == 0x20B:
            result["bitness"] = "64-bit"
            data_dir = optional + 112
        elif opt_magic == 0x10B:
            result["bitness"] = "32-bit"
            data_dir = optional + 96
        else:
            data_dir = None
            result["evidence"].append("Optional header no estandar")
        # La data directory #14 es la cabecera CLI: si apunta a algun lado, es .NET.
        if data_dir is not None and len(head) >= data_dir + 14 * 8 + 8:
            cli_va, cli_size = struct.unpack_from("<II", head, data_dir + 14 * 8)
            if cli_va or cli_size:
                result["is_dotnet"] = True
                result["evidence"].append(
                    f"Cabecera CLI (.NET) presente: VA=0x{cli_va:08x}, "
                    f"size={cli_size} bytes")
        return result

    @staticmethod
    def _detect_packer(sample: bytes) -> tuple[str, list[str]]:
        evidence: list[str] = []
        detected = ""
        for signature, name in _PACKERS:
            if signature in sample:
                evidence.append(
                    f"Firma de empaquetado encontrada: {signature!r} -> {name}")
                if not detected:
                    detected = name
        return detected, evidence

    def _inspect_zip(self, target: Path) -> tuple[tuple[dict, ...], dict]:
        entries: list[dict] = []
        notes: list[str] = []
        framework = ""
        try:
            with zipfile.ZipFile(target) as archive:
                infos = archive.infolist()
                for info in infos[:200]:
                    entries.append({
                        "name": info.filename,
                        "size": info.file_size,
                        "compressed": info.compress_size,
                        "directory": info.is_dir(),
                    })
                if len(infos) > 200:
                    notes.append(
                        f"ZIP con {len(infos)} entradas; se listan las primeras 200.")
                names = {info.filename for info in infos}
                if "AndroidManifest.xml" in names or any(n.endswith(".dex") for n in names):
                    framework = "APK (paquete Android)"
                elif "META-INF/MANIFEST.MF" in names:
                    framework = "JAR (archivo Java)"
                elif any(n.startswith("word/") for n in names):
                    framework = "DOCX (documento Office Open XML)"
                notes.append(f"ZIP valido con {len(infos)} entradas.")
        except (zipfile.BadZipFile, OSError) as exc:
            notes.append(f"Tiene firma ZIP pero no se pudo listar: {exc}")
        return tuple(entries), {"framework": framework, "notes": notes}

    @staticmethod
    def _extract_urls(sample: bytes) -> tuple[str, ...]:
        seen: list[str] = []
        for match in _URL_RE.finditer(sample):
            try:
                url = match.group().decode("ascii")
            except UnicodeDecodeError:
                continue
            url = url.rstrip(".,;:'\")]}")
            if url not in seen:
                seen.append(url)
            if len(seen) >= 60:
                break
        return tuple(seen)

    @staticmethod
    def _notable_strings(sample: bytes, urls: tuple[str, ...]) -> tuple[str, ...]:
        markers = ("/api/", "://", "token", "secret", "apikey", "api_key",
                   "bearer", "authorization", "endpoint", "webhook")
        candidates: list[str] = list(urls)
        seen = set(urls)
        for match in _ASCII_RE.finditer(sample):
            try:
                text = match.group().decode("ascii")
            except UnicodeDecodeError:
                continue
            low = text.lower()
            if any(token in low for token in markers):
                if text not in seen:
                    seen.add(text)
                    candidates.append(text)
            if len(candidates) >= 60:
                break
        return tuple(candidates[:60])

