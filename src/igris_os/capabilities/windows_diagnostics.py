"""Diagnostico y reparacion de Windows ejecutados por IGRIS.

No acepta comandos arbitrarios del modelo. Cada capacidad ejecuta una receta
fija, visible y auditable para impedir que una respuesta LLM pueda convertir
una peticion de diagnostico en una orden destructiva.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import textwrap

from igris_os.domain import ActionRisk, CapabilitySpec, ExecutionResult


BLOCKED_PATTERNS = (
    r"\bdiskpart\b.*?\bclean\b",
    r"\bclear-disk\b",
    r"\bremove-partition\b",
    r"\bdelete\s+partition\b",
    r"\bformat(?:\.com)?\b[^\r\n]*(?:\bc:|\\\\\.\\physicaldrive0)(?:\s|$)",
    r"\bdel\b[^\r\n]*\s/[sq]\b[^\r\n]*\bc:\\",
    r"\brd\b[^\r\n]*\s/[sq]\b[^\r\n]*\bc:\\",
)


def register_windows_diagnostic_capabilities(registry) -> None:
    registry.register(
        CapabilitySpec(
            "host.windows.diagnose",
            "Ejecuta un diagnostico real de Windows con PowerShell/CMD y evidencia",
            ActionRisk.READ_ONLY,
            timeout_seconds=1800,
            tags=("windows", "diagnostic", "powershell", "cmd"),
        ),
        diagnose_windows,
    )
    registry.register(
        CapabilitySpec(
            "host.windows.repair",
            "Repara la imagen y archivos protegidos de Windows con DISM y SFC",
            ActionRisk.EXTERNAL,
            requires_confirmation=True,
            timeout_seconds=3600,
            tags=("windows", "repair", "dism", "sfc"),
        ),
        repair_windows,
    )
    registry.register(
        CapabilitySpec(
            "host.windows.disk_repair",
            "Programa CHKDSK de reparacion para una unidad local y puede reiniciar",
            ActionRisk.EXTERNAL,
            requires_confirmation=True,
            timeout_seconds=300,
            tags=("windows", "disk", "chkdsk", "reboot"),
        ),
        schedule_disk_repair,
    )
    registry.register(
        CapabilitySpec(
            "host.windows.memory_diagnostic",
            "Abre el diagnostico oficial de memoria de Windows",
            ActionRisk.EXTERNAL,
            requires_confirmation=True,
            timeout_seconds=60,
            tags=("windows", "memory", "mdsched", "reboot"),
        ),
        open_memory_diagnostic,
    )


def contains_blocked_command(text: str) -> bool:
    value = str(text or "")
    return any(re.search(pattern, value, flags=re.I | re.S) for pattern in BLOCKED_PATTERNS)


def _windows_required() -> ExecutionResult | None:
    if os.name != "nt":
        return ExecutionResult.failure(
            "El diagnostico del PC requiere Windows.", "WINDOWS_REQUIRED")
    return None


def _is_admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _workspace(payload: dict, suffix: str) -> Path:
    raw = str(payload.get("workspace") or "").strip()
    if not raw:
        raise ValueError("Falta el workspace de la mision")
    root = Path(raw).resolve() / "windows_health" / suffix
    root.mkdir(parents=True, exist_ok=True)
    return root


def _ps_literal(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _write_script(root: Path, name: str, body: str) -> Path:
    path = root / name
    path.write_text(body.replace("\n", "\r\n"), encoding="utf-8-sig")
    return path


def _run_visible_powershell(script: Path, *, timeout: int) -> int:
    powershell = "powershell.exe"
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    completed = subprocess.run(
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=str(script.parent),
        timeout=timeout,
        check=False,
        creationflags=flags,
    )
    return int(completed.returncode)


def _load_summary(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def _diagnose_script(summary: Path, transcript: Path) -> str:
    return textwrap.dedent(f"""
        $ErrorActionPreference = 'Continue'
        $ProgressPreference = 'Continue'
        $summaryPath = {_ps_literal(summary)}
        $transcriptPath = {_ps_literal(transcript)}
        $checks = [ordered]@{{}}
        $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

        function Invoke-NativeCheck([string]$Name, [string]$Exe, [string[]]$Args) {{
            Write-Host "`n=== $Name ===" -ForegroundColor Cyan
            Write-Host ("CMD> " + $Exe + " " + ($Args -join ' ')) -ForegroundColor DarkGray
            & $Exe @Args
            $code = $LASTEXITCODE
            $script:checks[$Name] = [ordered]@{{ exit_code = $code; ok = ($code -eq 0) }}
        }}

        function Invoke-PSCheck([string]$Name, [scriptblock]$Block) {{
            Write-Host "`n=== $Name ===" -ForegroundColor Cyan
            try {{
                & $Block | Out-Host
                $script:checks[$Name] = [ordered]@{{ ok = $true }}
            }} catch {{
                Write-Host $_.Exception.Message -ForegroundColor Yellow
                $script:checks[$Name] = [ordered]@{{ ok = $false; error = $_.Exception.Message }}
            }}
        }}

        try {{ Start-Transcript -Path $transcriptPath -Force | Out-Null }} catch {{}}
        Write-Host "IGRIS - DIAGNOSTICO REAL DE WINDOWS" -ForegroundColor Green
        Write-Host ("Administrador: " + $isAdmin)
        Write-Host ("Inicio: " + (Get-Date))

        Invoke-PSCheck 'sistema' {{ Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,LastBootUpTime }}
        Invoke-PSCheck 'cpu' {{ Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed }}
        Invoke-PSCheck 'memoria' {{ Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory }}
        Invoke-PSCheck 'gpu' {{ Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM }}
        Invoke-PSCheck 'discos' {{ Get-CimInstance Win32_DiskDrive | Select-Object Model,Status,Size,InterfaceType }}
        Invoke-PSCheck 'volumenes' {{ Get-Volume | Select-Object DriveLetter,FileSystem,HealthStatus,SizeRemaining,Size }}
        Invoke-PSCheck 'discos_fisicos' {{ Get-PhysicalDisk | Select-Object FriendlyName,HealthStatus,OperationalStatus,MediaType,Size }}
        Invoke-PSCheck 'winsat' {{ Get-CimInstance Win32_WinSAT | Select-Object CPUScore,MemoryScore,DiskScore,GraphicsScore,D3DScore,WinSPRLevel }}
        Invoke-PSCheck 'drivers_con_problemas' {{ Get-PnpDevice -PresentOnly | Where-Object Status -ne 'OK' | Select-Object Status,Class,FriendlyName,InstanceId }}
        Invoke-PSCheck 'errores_sistema_7_dias' {{ Get-WinEvent -FilterHashtable @{{LogName='System'; Level=1,2; StartTime=(Get-Date).AddDays(-7)}} -MaxEvents 50 | Select-Object TimeCreated,Id,ProviderName,Message }}
        Invoke-NativeCheck 'plan_energia' 'powercfg.exe' @('/GETACTIVESCHEME')

        if ($isAdmin) {{
            Invoke-NativeCheck 'sfc_verifyonly' 'sfc.exe' @('/verifyonly')
            Invoke-NativeCheck 'dism_checkhealth' 'DISM.exe' @('/Online','/Cleanup-Image','/CheckHealth')
            Invoke-NativeCheck 'dism_scanhealth' 'DISM.exe' @('/Online','/Cleanup-Image','/ScanHealth')
            Invoke-NativeCheck 'chkdsk_scan' 'chkdsk.exe' @('C:','/scan')
        }} else {{
            $checks['admin_checks'] = [ordered]@{{ ok = $false; skipped = $true; reason = 'IGRIS no esta elevado como administrador' }}
            Write-Host "`n[AVISO] SFC, DISM y CHKDSK se omiten porque IGRIS no esta elevado." -ForegroundColor Yellow
        }}

        $result = [ordered]@{{
            mode = 'diagnose'
            administrator = $isAdmin
            computer = $env:COMPUTERNAME
            started = (Get-Date).ToString('o')
            checks = $checks
        }}
        $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
        Write-Host "`nInforme: $transcriptPath" -ForegroundColor Green
        try {{ Stop-Transcript | Out-Null }} catch {{}}
    """).strip() + "\n"


def _repair_script(summary: Path, transcript: Path) -> str:
    return textwrap.dedent(f"""
        $ErrorActionPreference = 'Continue'
        $summaryPath = {_ps_literal(summary)}
        $transcriptPath = {_ps_literal(transcript)}
        $checks = [ordered]@{{}}
        $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        if (-not $isAdmin) {{
            [ordered]@{{ mode='repair'; administrator=$false; error='ADMIN_REQUIRED' }} | ConvertTo-Json | Set-Content -LiteralPath $summaryPath -Encoding UTF8
            Write-Host '[ERROR] Ejecuta IGRIS como administrador.' -ForegroundColor Red
            exit 5
        }}
        function Invoke-Native([string]$Name, [string]$Exe, [string[]]$Args) {{
            Write-Host "`n=== $Name ===" -ForegroundColor Cyan
            Write-Host ("CMD> " + $Exe + " " + ($Args -join ' ')) -ForegroundColor DarkGray
            & $Exe @Args
            $code = $LASTEXITCODE
            $script:checks[$Name] = [ordered]@{{ exit_code=$code; ok=($code -eq 0 -or $code -eq 3010) }}
            return $code
        }}
        try {{ Start-Transcript -Path $transcriptPath -Force | Out-Null }} catch {{}}
        Write-Host 'IGRIS - REPARACION DE WINDOWS' -ForegroundColor Green
        $dism = Invoke-Native 'dism_restorehealth' 'DISM.exe' @('/Online','/Cleanup-Image','/RestoreHealth')
        if ($dism -eq 0 -or $dism -eq 3010) {{
            [void](Invoke-Native 'sfc_scannow' 'sfc.exe' @('/scannow'))
        }} else {{
            Write-Host '[AVISO] SFC no se ejecuta porque DISM no termino correctamente.' -ForegroundColor Yellow
        }}
        [void](Invoke-Native 'chkdsk_scan' 'chkdsk.exe' @('C:','/scan'))
        $result = [ordered]@{{ mode='repair'; administrator=$true; checks=$checks; completed=(Get-Date).ToString('o') }}
        $result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
        try {{ Stop-Transcript | Out-Null }} catch {{}}
    """).strip() + "\n"


def diagnose_windows(payload: dict) -> ExecutionResult:
    denied = _windows_required()
    if denied:
        return denied
    try:
        root = _workspace(payload, "diagnose")
        summary = root / "summary.json"
        transcript = root / "transcript.txt"
        script = _write_script(root, "IGRIS_DIAGNOSTICO_WINDOWS.ps1",
                               _diagnose_script(summary, transcript))
        code = _run_visible_powershell(script, timeout=1700)
        data = _load_summary(summary)
        if not data:
            return ExecutionResult.failure(
                f"PowerShell termino sin generar informe (codigo {code}).",
                "WINDOWS_DIAGNOSTIC_NO_REPORT",
                data={"script": str(script), "transcript": str(transcript)},
            )
        message = "Diagnostico de Windows completado con evidencia local."
        if not data.get("administrator", False):
            message += " IGRIS no estaba elevado: SFC/DISM/CHKDSK fueron omitidos."
        return ExecutionResult.success(
            message,
            diagnostic=data,
            report=str(transcript),
            summary=str(summary),
            script=str(script),
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult.failure(
            "El diagnostico de Windows excedio el tiempo permitido.",
            "WINDOWS_DIAGNOSTIC_TIMEOUT")
    except (OSError, ValueError) as exc:
        return ExecutionResult.failure(str(exc), "WINDOWS_DIAGNOSTIC_FAILED")


def repair_windows(payload: dict) -> ExecutionResult:
    denied = _windows_required()
    if denied:
        return denied
    if not _is_admin():
        return ExecutionResult.failure(
            "La reparacion necesita IGRIS ejecutado como administrador.",
            "WINDOWS_ADMIN_REQUIRED")
    try:
        root = _workspace(payload, "repair")
        summary = root / "summary.json"
        transcript = root / "transcript.txt"
        script = _write_script(root, "IGRIS_REPARAR_WINDOWS.ps1",
                               _repair_script(summary, transcript))
        code = _run_visible_powershell(script, timeout=3500)
        data = _load_summary(summary)
        if not data:
            return ExecutionResult.failure(
                f"La reparacion termino sin informe (codigo {code}).",
                "WINDOWS_REPAIR_NO_REPORT",
                data={"script": str(script), "transcript": str(transcript)},
            )
        failed = [name for name, item in data.get("checks", {}).items()
                  if isinstance(item, dict) and not item.get("ok", False)]
        if failed:
            return ExecutionResult.failure(
                "La reparacion termino con comprobaciones fallidas: " + ", ".join(failed),
                "WINDOWS_REPAIR_INCOMPLETE",
                data={"diagnostic": data, "report": str(transcript), "summary": str(summary)},
            )
        return ExecutionResult.success(
            "DISM y SFC terminaron; se ejecuto un nuevo CHKDSK /scan.",
            diagnostic=data,
            report=str(transcript),
            summary=str(summary),
            script=str(script),
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult.failure(
            "La reparacion de Windows excedio el tiempo permitido.",
            "WINDOWS_REPAIR_TIMEOUT")
    except (OSError, ValueError) as exc:
        return ExecutionResult.failure(str(exc), "WINDOWS_REPAIR_FAILED")


def _drive_letter(value: str) -> str:
    raw = str(value or "C:").strip().upper().rstrip("\\/")
    if re.fullmatch(r"[A-Z]:", raw):
        return raw
    raise ValueError("Unidad no valida; usa una letra como C:")


def schedule_disk_repair(payload: dict) -> ExecutionResult:
    denied = _windows_required()
    if denied:
        return denied
    if not _is_admin():
        return ExecutionResult.failure(
            "CHKDSK de reparacion necesita IGRIS ejecutado como administrador.",
            "WINDOWS_ADMIN_REQUIRED")
    try:
        drive = _drive_letter(payload.get("drive", "C:"))
        recover = bool(payload.get("recover_bad_sectors", False))
        reboot = bool(payload.get("reboot", False))
        root = _workspace(payload, "disk_repair")
        transcript = root / "chkdsk.txt"
        args = [drive, "/f"] + (["/r"] if recover else [])
        command = "chkdsk.exe " + " ".join(args)
        # En la unidad del sistema, CHKDSK puede pedir programar la comprobacion.
        # Se usa la letra afirmativa del idioma de la interfaz para contestar.
        script_text = textwrap.dedent(f"""
            $ErrorActionPreference = 'Continue'
            try {{ Start-Transcript -Path {_ps_literal(transcript)} -Force | Out-Null }} catch {{}}
            $lang = [Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName
            $yes = switch ($lang) {{ 'es' {{'S'}} 'fr' {{'O'}} 'de' {{'J'}} 'it' {{'S'}} 'pt' {{'S'}} default {{'Y'}} }}
            Write-Host 'IGRIS - REPARACION DE DISCO' -ForegroundColor Green
            Write-Host 'CMD> {command}' -ForegroundColor DarkGray
            cmd.exe /d /c ("echo " + $yes + "|{command}")
            $code = $LASTEXITCODE
            Write-Host ("Codigo CHKDSK: " + $code)
            try {{ Stop-Transcript | Out-Null }} catch {{}}
            exit $code
        """).strip() + "\n"
        script = _write_script(root, "IGRIS_CHKDSK.ps1", script_text)
        code = _run_visible_powershell(script, timeout=240)
        if reboot:
            subprocess.run(
                ["shutdown.exe", "/r", "/t", "60", "/c",
                 "IGRIS: reinicio autorizado para completar la comprobacion del disco."],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        return ExecutionResult.success(
            "CHKDSK de reparacion solicitado" + ("; reinicio programado en 60 segundos." if reboot else "."),
            command=command,
            exit_code=code,
            reboot_scheduled=reboot,
            report=str(transcript),
            script=str(script),
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult.failure(
            "CHKDSK no devolvio control a tiempo.", "WINDOWS_CHKDSK_TIMEOUT")
    except (OSError, ValueError) as exc:
        return ExecutionResult.failure(str(exc), "WINDOWS_CHKDSK_FAILED")


def open_memory_diagnostic(payload: dict) -> ExecutionResult:
    denied = _windows_required()
    if denied:
        return denied
    try:
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        subprocess.Popen(["mdsched.exe"], creationflags=flags)
        return ExecutionResult.success(
            "Se ha abierto Diagnostico de memoria de Windows. Windows requiere elegir en su dialogo si reiniciar ahora o comprobar en el siguiente arranque.",
            tool="mdsched.exe",
            reboot_controlled_by_windows_dialog=True,
        )
    except OSError as exc:
        return ExecutionResult.failure(str(exc), "WINDOWS_MEMORY_DIAGNOSTIC_FAILED")
