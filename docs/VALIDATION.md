# Evidencia de validacion

Fecha: 2026-08-14.

## Puertas aprobadas

- Suite unitaria, integración y seguridad: 106 pruebas aprobadas.
- Arranque del panel PyQt6 en modo offscreen: aprobado.
- Build PyInstaller para Windows: aprobado.
- Arranque del ejecutable y captura visual: aprobado.
- Ollama local con seleccion automatica de modelo: aprobado.
- Mision real con qwen2.5-coder:7b: proyecto Python generado, probado y entregado.
- FFmpeg real: video sintetico, inspeccion y miniatura: aprobado.
- Inventario: cinco fuentes IGRIS y 2676 archivos catalogados.
- Comprobación de release, codificación UTF-8 y recursos obligatorios: aprobada.
- Voz Microsoft Pablo mediante SAPI de escritorio: aprobada.
- Persistencia portable anclada al ejecutable: aprobada.
- Plantilla Godot 2D jugable y evidencia `VERIFICATION.json`: aprobada.
- Pipeline FFmpeg real con miniatura, transcodificación, evidencia y rollback:
  aprobado.
- Autoanálisis del repositorio IGRIS: 85 archivos, 304 símbolos y 23 archivos
  de prueba mapeados; búsqueda de seguridad localizada correctamente.
- Edición real con qwen coder sobre copia aislada: función añadida, diff generado,
  verificación aprobada y original intacto.
- Copia aislada real del repositorio: 101 archivos con hashes verificados.
- Cola recuperable, memoria técnica y evolución en cuarentena: aprobadas.
- Coordinación especializada, revisión cruzada, progreso, cancelación segura y
  géneros Godot seleccionables: aprobados.

## Comandos reproducibles

    python tools/quality_gate.py
    python -m igris_os health
    python -m igris_os capabilities
    python -m igris_os panel
    .\build_portable.ps1

Cada build genera `SHA256SUMS.txt` junto al ejecutable para comprobar su
integridad antes de distribuirlo.

Los artefactos temporales y datos de usuario permanecen en runtime y no se
incluyen en Git. No se ha eliminado ninguna version anterior.
