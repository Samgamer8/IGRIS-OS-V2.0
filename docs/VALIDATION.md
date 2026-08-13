# Evidencia de validacion

Fecha: 2026-08-14.

## Puertas aprobadas

- Suite unitaria y de seguridad: 43 pruebas aprobadas.
- Arranque del panel PyQt6 en modo offscreen: aprobado.
- Build PyInstaller para Windows: aprobado.
- Arranque del ejecutable y captura visual: aprobado.
- Ollama local con seleccion automatica de modelo: aprobado.
- Mision real con qwen2.5-coder:7b: proyecto Python generado, probado y entregado.
- FFmpeg real: video sintetico, inspeccion y miniatura: aprobado.
- Inventario: cinco fuentes IGRIS y 2676 archivos catalogados.

## Comandos reproducibles

    python tools/quality_gate.py
    python -m igris_os health
    python -m igris_os capabilities
    python -m igris_os panel
    .\build_portable.ps1

Los artefactos temporales y datos de usuario permanecen en runtime y no se
incluyen en Git. No se ha eliminado ninguna version anterior.
