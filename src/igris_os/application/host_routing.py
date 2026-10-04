"""Ordenes locales que no requieren que un modelo invente comandos o rutas."""
import re
import unicodedata


def _normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if unicodedata.category(c) != "Mn").strip()


def _windows_diagnostic_action(objective, text):
    from igris_os.application.mission_router import RoutedAction
    pc_markers = (
        "mi pc", "el pc", "del pc", "este pc", "mi ordenador", "el ordenador",
        "del ordenador", "este ordenador", "mi equipo", "el equipo", "del equipo",
        "windows", "sistema operativo",
    )
    diagnostic_markers = (
        "diagnostico", "diagnosticar", "comprueba", "comprobar", "revisa", "revisar",
        "chequea", "chequear", "estado", "pruebas necesarias", "prueba el sistema",
        "averigua", "averiguar", "analiza", "analizar",
    )
    shell_markers = ("cmd", "powershell", "sfc", "dism", "chkdsk", "mdsched")
    pc_context = any(marker in text for marker in pc_markers)
    diagnostic = any(marker in text for marker in diagnostic_markers)
    shell_context = any(marker in text for marker in shell_markers)

    if "mdsched" in text or (pc_context and "memoria" in text and "diagnost" in text):
        return RoutedAction("capability", "host.windows.memory_diagnostic", {}, True)

    if "chkdsk" in text and any(flag in text for flag in ("/f", "/r", "repara", "reparar")):
        recover = "/r" in text or "sectores" in text
        reboot = any(phrase in text for phrase in (
            "reinicia", "reiniciar", "aunque tenga que reiniciar", "reinicio autorizado"))
        drive_match = re.search(r"\b([a-z]):(?:\\|\b)", text)
        drive = (drive_match.group(1).upper() + ":") if drive_match else "C:"
        return RoutedAction(
            "capability", "host.windows.disk_repair",
            {"drive": drive, "recover_bad_sectors": recover, "reboot": reboot}, True)

    repair_words = ("repara", "reparar", "arregla", "arreglar", "corrige", "corregir",
                    "restorehealth", "scannow")
    if (pc_context or shell_context) and any(word in text for word in repair_words):
        return RoutedAction("capability", "host.windows.repair", {}, True)

    if (pc_context and diagnostic) or (diagnostic and shell_context):
        return RoutedAction(
            "capability", "host.windows.diagnose", {"visible_console": True})
    return None


def host_action(objective):
    from igris_os.application.mission_router import RoutedAction
    text = _normalize(objective)
    windows = _windows_diagnostic_action(objective, text)
    if windows:
        return windows
    if any(phrase in text for phrase in (
            "recursos de mi pc", "recursos del equipo", "revisa mi pc", "inspecciona mi pc",
            "hardware de mi pc", "memoria disponible", "acceso a mi pc")):
        return RoutedAction("capability", "host.inventory")
    # Quoted paths are unambiguous, including names with spaces and accents.
    quoted = re.findall(r'"([^"\r\n]+)"', objective)
    paths = [p for p in quoted if re.match(r"^(?:[A-Za-z]:[\\/]|/|\\\\)", p)]
    if not paths:
        match = re.search(r"(?:[A-Za-z]:[\\/]|/)[^\r\n\"<>|]+", objective)
        if match:
            paths = [match.group(0).strip()]
    for verbs, name in ((r"(?:lista|muestra carpeta)", "list"),
                        (r"(?:lee|lee archivo)", "read"),
                        (r"(?:abre|ejecuta|abre programa)", "open"),
                        (r"(?:crea carpeta|crea la carpeta|crea una carpeta)", "mkdir")):
        if re.match(r"^(?:ok[, ]+)?" + verbs + r"\s", text) and paths:
            return RoutedAction("capability", "host." + name, {"path": paths[0]}, name in {"open", "mkdir"})
    if re.match(r"^(?:ok[, ]+)?copia\s", text) and len(paths) == 2:
        return RoutedAction("capability", "host.copy", {"source": paths[0], "target": paths[1]}, True)
    search = re.match(r'^(?:ok[, ]+)?(?:busca|buscar|localiza)\s+(.+?)(?:\s+en\s+.+)?$', objective, re.I)
    if search:
        pattern = search.group(1).strip().strip('"')
        if pattern.casefold().startswith("archivo "):
            pattern = pattern[8:]
        if "plantillas" not in text and "templates" not in text:
            return RoutedAction("capability", "host.find", {"pattern": pattern, "root": paths[0] if paths else ""})
    return None


def host_confirmation(capability, payload):
    if capability == "host.windows.repair":
        return (
            "IGRIS ejecutara en una consola visible DISM /Online /Cleanup-Image /RestoreHealth, "
            "despues sfc /scannow y finalmente chkdsk C: /scan. Estas herramientas pueden "
            "reparar archivos de Windows. ¿Autorizar la reparacion?")
    if capability == "host.windows.disk_repair":
        command = "chkdsk " + str(payload.get("drive", "C:")) + " /f"
        if payload.get("recover_bad_sectors"):
            command += " /r"
        tail = " y reiniciara el PC en 60 segundos" if payload.get("reboot") else ""
        return ("IGRIS ejecutara " + command + tail + ". La comprobacion puede tardar bastante. "
                "¿Autorizar?")
    if capability == "host.windows.memory_diagnostic":
        return ("IGRIS abrira el Diagnostico de memoria de Windows (mdsched). Windows mostrara "
                "su dialogo oficial para elegir el reinicio. ¿Continuar?")
    lines = ["Operacion local: " + capability]
    lines.extend(str(key) + ": " + str(value) for key, value in payload.items()
                 if not str(key).startswith("__"))
    lines.append("Se usaran los permisos actuales de tu cuenta de Windows. ¿Continuar?")
    return "\n".join(lines)
