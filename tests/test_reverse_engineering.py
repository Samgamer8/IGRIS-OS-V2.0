"""Tests del analizador de artefactos y las capacidades de reverse engineering.

Ningun test toca la red ni binarios del sistema: se construyen artefactos
sinteticos (un PE minimo valido, un ZIP real, un texto) en un directorio
temporal. Verifica que los hechos son reales (magic bytes, cabecera PE,
contenido ZIP, URLs) y que las limitaciones se declaran en lugar de inventar.
"""
import struct
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from igris_os.files import ArtifactAnalyzer


def _make_pe(path: Path, *, machine: int = 0x8664, dotnet: bool = False) -> Path:
    """Construye un PE minimo pero con cabeceras reales y parseables."""
    buf = bytearray(b"\x00" * 0x400)
    buf[0:2] = b"MZ"
    e_lfanew = 0x80
    struct.pack_into("<I", buf, 0x3C, e_lfanew)
    buf[e_lfanew:e_lfanew + 4] = b"PE\x00\x00"
    coff = e_lfanew + 4
    struct.pack_into("<HHI", buf, coff, machine, 3, 0x5F000000)
    optional = coff + 20
    # Optional header PE32+ (0x20B). Rellenamos hasta la data directory.
    struct.pack_into("<H", buf, optional, 0x20B)
    data_dir = optional + 112
    if dotnet:
        # Data directory #14 (CLI header) apunta a algun sitio -> es .NET.
        struct.pack_into("<II", buf, data_dir + 14 * 8, 0x2000, 0x48)
    buf += b"https://api.example.com/v1/ping\x00secret_token_value_here\x00"
    path.write_bytes(bytes(buf))
    return path


class TestArtifactAnalyzer(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = ArtifactAnalyzer()

    def test_detects_pe_architecture_and_bitness(self):
        with TemporaryDirectory() as directory:
            exe = _make_pe(Path(directory) / "app.exe", machine=0x8664)
            report = self.analyzer.analyze(exe)
            self.assertEqual(report.kind, "pe")
            self.assertEqual(report.architecture, "x64 (AMD64)")
            self.assertEqual(report.bitness, "64-bit")
            self.assertEqual(report.sections, 3)
            self.assertFalse(report.is_dotnet)
            self.assertEqual(len(report.sha256), 64)

    def test_detects_dotnet_via_cli_header(self):
        with TemporaryDirectory() as directory:
            exe = _make_pe(Path(directory) / "managed.exe", dotnet=True)
            report = self.analyzer.analyze(exe)
            self.assertTrue(report.is_dotnet)
            self.assertTrue(any("CLI" in note for note in report.notes))

    def test_extracts_urls_and_declares_limits(self):
        with TemporaryDirectory() as directory:
            exe = _make_pe(Path(directory) / "net.exe")
            report = self.analyzer.analyze(exe)
            self.assertIn("https://api.example.com/v1/ping", report.urls)
            # El limite honesto siempre se declara.
            self.assertTrue(any("desensamblado" in lim for lim in report.limitations))

    def test_zip_lists_entries_and_detects_apk(self):
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "app.apk"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("AndroidManifest.xml", "<manifest/>")
                zf.writestr("classes.dex", "dex\n035")
                zf.writestr("assets/config.json", "{}")
            report = self.analyzer.analyze(archive)
            self.assertEqual(report.kind, "zip")
            self.assertEqual(report.framework, "APK (paquete Android)")
            names = {entry["name"] for entry in report.zip_entries}
            self.assertIn("AndroidManifest.xml", names)

    def test_detects_text_file(self):
        with TemporaryDirectory() as directory:
            text = Path(directory) / "notes.txt"
            text.write_text("hola mundo, esto es texto plano\n" * 3, encoding="utf-8")
            report = self.analyzer.analyze(text)
            self.assertEqual(report.kind, "text")

class TestReverseCapabilities(unittest.TestCase):
    def _handler(self, name: str):
        from igris_os.capabilities import reverse_engineering as module

        registry = {}

        class _Reg:
            def register(self, spec, handler):
                registry[spec.name] = (spec, handler)

        module.register_reverse_engineering(_Reg())
        return registry[name][1]

    def test_reverse_inspect_success(self):
        with TemporaryDirectory() as directory:
            archive = Path(directory) / "app.apk"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("AndroidManifest.xml", "<m/>")
            handler = self._handler("reverse.inspect")
            result = handler({"path": str(archive)})
            self.assertTrue(result.ok)
            self.assertEqual(result.data["reverse_inspect"]["kind"], "zip")

    def test_reverse_inspect_invalid_path(self):
        handler = self._handler("reverse.inspect")
        result = handler({"path": "C:\\no\\existe\\nada.aqu\\"})
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "REVERSE_INSPECT_FAILED")

    def test_reverse_project_maps_source(self):
        with TemporaryDirectory() as directory:
            project = Path(directory) / "proj"
            project.mkdir()
            (project / "main.py").write_text(
                "import os\n\n\ndef run():\n    return 1\n", encoding="utf-8")
            workspace = Path(directory) / "ws"
            handler = self._handler("reverse.project")
            result = handler({"workspace": str(workspace), "root": str(project)})
            self.assertTrue(result.ok)
            data = result.data["reverse_project"]
            self.assertGreaterEqual(data["files"], 1)
            self.assertIn("python", data["languages"])

    def test_reverse_project_invalid_root(self):
        with TemporaryDirectory() as directory:
            handler = self._handler("reverse.project")
            result = handler({"workspace": directory,
                              "root": str(Path(directory) / "missing")})
            self.assertFalse(result.ok)
            self.assertEqual(result.code, "REVERSE_PROJECT_INVALID")


if __name__ == "__main__":
    unittest.main()


    def test_rejects_directory(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                self.analyzer.analyze(Path(directory))

    def test_packer_signature_reported_as_evidence(self):
        with TemporaryDirectory() as directory:
            blob = Path(directory) / "packed.bin"
            blob.write_bytes(b"MZ" + b"\x00" * 100 + b"pyi-bootloader_here" + b"\x00" * 50)
            report = self.analyzer.analyze(blob)
            self.assertEqual(report.packer, "PyInstaller")
            self.assertTrue(any("PyInstaller" in note for note in report.notes))
