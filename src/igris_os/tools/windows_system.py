from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True, slots=True)
class SystemCapability:
    name: str
    available: bool
    version: str = ""
    path: str = ""


@dataclass(frozen=True, slots=True)
class PrivilegedResult:
    ok: bool
    message: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class WindowsSystemAccess:
    def __init__(self, *, require_admin: bool = False) -> None:
        self.require_admin = require_admin
        self._is_admin = self._check_admin()

    def list_drivers(self) -> list[dict]:
        if not self._is_admin and self.require_admin:
            return []
        try:
            out = subprocess.run(
                ["powershell", "-Command",
                 "Get-WmiObject Win32_PnPSignedDriver | Select-Object DeviceName, DriverVersion, Manufacturer | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if out.returncode == 0:
                data = json.loads(out.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [{"name": d.get("DeviceName", ""),
                         "version": d.get("DriverVersion", ""),
                         "manufacturer": d.get("Manufacturer", "")}
                        for d in data[:50]]
        except Exception:
            pass
        return []

    def list_installed_software(self) -> list[dict]:
        try:
            out = subprocess.run(
                ["powershell", "-Command",
                 "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*, HKLM:\\Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | Select-Object DisplayName, DisplayVersion, Publisher | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if out.returncode == 0:
                data = json.loads(out.stdout)
                if isinstance(data, dict):
                    data = [data]
                return [{"name": d.get("DisplayName", ""),
                         "version": d.get("DisplayVersion", ""),
                         "publisher": d.get("Publisher", "")}
                        for d in data if d.get("DisplayName")]
        except Exception:
            pass
        return []

    def system_info(self) -> dict:
        info = {
            "os": sys.platform,
            "admin": self._is_admin,
            "python": sys.version,
            "cpu_count": os.cpu_count(),
        }
        try:
            out = subprocess.run(
                ["powershell", "-Command",
                 "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if out.returncode == 0:
                info["ram_gb"] = float(out.stdout.strip())
        except Exception:
            info["ram_gb"] = 0.0
        return info

    def install_msi(self, msi_path: Path, *, silent: bool = True) -> PrivilegedResult:
        if not msi_path.exists():
            return PrivilegedResult(False, "MSI no existe")
        if self.require_admin and not self._is_admin:
            return PrivilegedResult(False, "Se requieren privilegios de admin")
        cmd = ["msiexec", "/i", str(msi_path)]
        if silent:
            cmd.extend(["/quiet", "/norestart"])
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=300, check=False)
            return PrivilegedResult(result.returncode == 0,
                                    "Instalacion " + ("exitosa" if result.returncode == 0 else "fallida"),
                                    result.stdout.strip(), result.stderr.strip(),
                                    result.returncode)
        except subprocess.TimeoutExpired:
            return PrivilegedResult(False, "timeout")
        except Exception as exc:
            return PrivilegedResult(False, str(exc))

    def uninstall_by_name(self, name: str) -> PrivilegedResult:
        if self.require_admin and not self._is_admin:
            return PrivilegedResult(False, "Se requieren privilegios de admin")
        if not re.fullmatch(r"[A-Za-z0-9 \.\-\(\)\[\]_+]+", name or ""):
            return PrivilegedResult(False, "Nombre de paquete invalido")
        try:
            cmd = [
                "powershell", "-Command",
                f"Get-WmiObject Win32_Product | Where-Object Name -like '*{name}*' | ForEach-Object {{ $_.Uninstall() }}"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=120, check=False)
            return PrivilegedResult(result.returncode == 0,
                                    "Desinstalacion " + ("exitosa" if result.returncode == 0 else "fallida"),
                                    result.stdout.strip(), result.stderr.strip(),
                                    result.returncode)
        except Exception as exc:
            return PrivilegedResult(False, str(exc))

    @staticmethod
    def _check_admin() -> bool:
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False


class DependencyManager:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.lock_file = self.root / "dependencies.lock.json"
        self.sbom_file = self.root / "sbom.json"

    def resolve(self, language: str, manifest: dict) -> dict:
        if language == "rust":
            return self._resolve_rust(manifest)
        if language == "node":
            return self._resolve_node(manifest)
        if language == "python":
            return self._resolve_python(manifest)
        return {"ok": False, "message": f"Sin gestor para {language}"}

    def update_lock(self, language: str, dependencies: Sequence[str]) -> None:
        lock = {}
        if self.lock_file.exists():
            try:
                lock = json.loads(self.lock_file.read_text(encoding="utf-8"))
            except Exception:
                lock = {}
        lock[language] = {
            "dependencies": list(dependencies),
            "updated_at": __import__("datetime").datetime.now().isoformat(),
        }
        self.lock_file.write_text(
            json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8",
        )

    def generate_sbom(self, components: Sequence[dict]) -> str:
        sbom = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "components": list(components),
        }
        self.sbom_file.write_text(
            json.dumps(sbom, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        return str(self.sbom_file)

    def _resolve_rust(self, manifest: dict) -> dict:
        cargo_toml = self.root / "Cargo.toml"
        if not cargo_toml.exists():
            cargo_toml.write_text("[package]\nname = \"app\"\nversion = \"0.1.0\"\n", encoding="utf-8")
        return {"ok": True, "file": "Cargo.toml", "action": "created"}

    def _resolve_node(self, manifest: dict) -> dict:
        package_json = self.root / "package.json"
        if not package_json.exists():
            package_json.write_text(
                json.dumps({"name": "app", "version": "0.1.0",
                            "dependencies": manifest.get("dependencies", {}),
                            "devDependencies": manifest.get("devDependencies", {})},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return {"ok": True, "file": "package.json", "action": "created"}

    def _resolve_python(self, manifest: dict) -> dict:
        requirements = self.root / "requirements.txt"
        if not requirements.exists():
            deps = manifest.get("dependencies", [])
            requirements.write_text("\n".join(deps) + "\n", encoding="utf-8")
        return {"ok": True, "file": "requirements.txt", "action": "created"}
