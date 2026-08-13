# IGRIS OS V2.O

IGRIS OS es una capa operativa de inteligencia artificial para Windows. Convierte
ordenes en misiones verificables, aplica permisos antes de ejecutar herramientas y
registra resultados auditables.

Esta carpeta es la unica base canonica de la reconstruccion. Las versiones antiguas
son fuentes de migracion y no se copian completas.

## Estado

Primera base ejecutable:

- contratos de mision, capacidad y resultado;
- registro de capacidades;
- politica de riesgos y confirmacion;
- workspace aislado por mision;
- auditoria JSONL;
- diagnostico local de solo lectura;
- CLI y pruebas unitarias/de seguridad.
- taller Python con verificacion aislada;
- indexacion segura de archivos y memoria SQLite verificada;
- proveedor Ollama local;
- adaptadores detectables para FFmpeg, Blender, Godot y Git;
- laboratorio de evolucion con promocion solo por mejora medida;
- panel militar PyQt6 conectado al director de misiones;
- voz masculina española Microsoft Pablo y dictado local de Windows;
- memoria persistente y auditoría consultable de misiones;
- adjuntos conectados a análisis, imagen, vídeo y audio;
- plantilla Godot 2D jugable con verificación;
- esquema de continuidad en `docs/SESSION_CONTINUITY.md`.

## Uso de desarrollo

```powershell
python -m pytest
$env:PYTHONPATH = "src"
python -m igris_os health
python -m igris_os capabilities
python -m igris_os plan "construye un programa Python con pruebas"
python -m igris_os providers
python -m igris_os inventory --source "C:\ruta\IGRIS"
python -m igris_os panel
python tools/quality_gate.py
```

No contiene claves, modelos, builds ni datos personales.
