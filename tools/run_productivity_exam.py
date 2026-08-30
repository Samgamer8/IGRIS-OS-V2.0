from __future__ import annotations

import json
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from igris_os.application import ProjectWorkspace
from igris_os.bootstrap import build_igris
from igris_os.domain import Mission
from igris_os.games import GodotExporter, GodotRuntime


DELIVERIES = ROOT / "proyectos"
MODEL = "qwen2.5-coder:14b"

EXAMS = (
    (
        "ajedrez",
        "games.godot.scaffold",
        {
            "name": "ajedrez",
            "genre": "top_down",
            "generate_full_code": True,
            "delivery_root": str(DELIVERIES),
            "objective": (
                "Crea un juego de ajedrez 3D completo y ejecutable en Godot 4. "
                "Incluye tablero y piezas distinguibles, posicion inicial legal, "
                "seleccion y movimientos por turnos, validacion de movimientos y "
                "capturas, reinicio, historial y README. No entregues una escena "
                "decorativa ni pseudocodigo."
            ),
            "model": MODEL,
        },
    ),
    (
        "programa",
        "programming.python.multifile.develop",
        {
            "model": MODEL,
            "timeout": 240,
            "fallback_models": ["deepseek-coder-v2:16b"],
            "delivery_root": str(DELIVERIES),
            "delivery_name": "programa",
            "answers": {
                "name": "programa",
                "technology": "python",
                "delivery": "source",
                "destination": str(DELIVERIES),
                "acceptance": (
                    "diagnostico de CPU, memoria, disco y procesos;"
                    "modo simulacion sin cambios;"
                    "confirmacion antes de cambios;"
                    "rollback y auditoria;"
                    "pruebas pytest ejecutables"
                ),
            },
            "objective": (
                "Crea un programa completo de optimizacion segura de PC para Windows. "
                "Debe diagnosticar CPU, memoria, disco y procesos, mostrar un informe "
                "antes de actuar, ofrecer simulacion, limitar acciones a limpieza "
                "reversible de temporales propios, exigir confirmacion, registrar "
                "acciones y permitir rollback. Incluye README, tests y ejecucion local."
            ),
        },
    ),
)


def run_exam() -> dict[str, object]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=("ajedrez", "programa"))
    parser.add_argument("--model", default=MODEL)
    selected = parser.parse_args()
    DELIVERIES.mkdir(parents=True, exist_ok=True)
    workspace = ProjectWorkspace(ROOT)
    kernel = build_igris(ROOT / "runtime")
    results: list[dict[str, object]] = []
    exams = tuple(item for item in EXAMS
                  if not selected.only or item[0] == selected.only)
    for name, capability, payload in exams:
        payload = dict(payload)
        payload["model"] = selected.model
        started = time.monotonic()
        mission = Mission(f"Examen real: crear {name}")
        approval = kernel.issue_approval(mission.objective, capability)
        result = kernel.execute(mission, capability, payload, approval=approval)
        if name == "ajedrez" and result.ok:
            project = Path(result.data.get("project", ""))
            runtime = GodotRuntime()
            executable = project / "ajedrez.exe"
            export = GodotExporter(runtime).export(
                project, executable, confirmed=True,
            ) if runtime.available else None
            result.data["godot_available"] = runtime.available
            result.data["executable"] = str(executable) if executable.is_file() else ""
            result.data["executable_verified"] = bool(
                export and export.verified)
            if not result.data["executable_verified"]:
                result.ok = False
                result.code = "GAME_EXECUTABLE_UNVERIFIED"
                result.message = (
                    "Ajedrez generado, pero no es entregable: falta un .exe "
                    "verificado o un playtest Godot reproducible.")
        results.append({
            "name": name,
            "capability": capability,
            "ok": result.ok,
            "code": result.code,
            "message": result.message,
            "duration_seconds": round(time.monotonic() - started, 3),
            "data": result.data,
        })
        if result.ok:
            workspace.create_project(name, (
                f"Generar {name}", "Ejecutar verificacion", "Revisar entrega",
            ))
    report = {
        "kind": "igris_productivity_exam",
        "model": selected.model,
        "delivery_root": str(DELIVERIES),
        "passed": bool(results) and all(item["ok"] for item in results),
        "results": results,
        "limitations": [
            "El proyecto panel_de_control requiere un adaptador de entrega web verificada.",
            "La disponibilidad de Godot determina el playtest visual.",
        ],
    }
    report_path = ROOT / "runtime" / "audit" / "productivity_exam_2026-08-26.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_exam(), ensure_ascii=False, indent=2))
