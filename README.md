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
- pipeline multimedia con previsualización, evidencia y rollback confinado;
- mapa profundo de repositorios con lenguajes, símbolos, dependencias y pruebas;
- recuperación semántica local (n-gramas hasheados y embeddings Ollama opcionales
  con autoselección del modelo) conectada a la misión contextual del panel;
- copias aisladas de repositorios y propuestas verificadas con diff y rollback;
- cola persistente de misiones y memoria técnica verificada;
- progreso monotónico y cancelación cooperativa en puntos seguros;
- coordinación de especialistas con revisión cruzada documentada;
- proyectos Godot top-down, arcade y plataformas;
- evolución medida en cuarentena, sin autopromoción a producción;
- plantilla Godot 2D jugable con verificación;
- playtest Godot automático (arranque headless + captura + comparación con
  referencia) con Godot portable en `.tools/godot/` (ignorado por Git);
- exportación a ejecutable Windows verificada (cabecera PE + lanzamiento real)
  usando plantillas oficiales instaladas en `%APPDATA%/Godot/export_templates`;
- enrutado de modelos por dificultad, tarea y presupuesto de tokens
  (local prioritario, con modos ahorro/calidad);
- verificador independiente: un segundo modelo aprueba o rechaza cada entrega
  con puntuación y umbral (el generador no se aprueba a sí mismo);
- sandbox de ejecución con Job Objects de Windows: límites de memoria/CPU y
  cierre forzado de procesos hijos (más allá de la lista negra de comandos);
- toolchain portátil en `.tools/`: Rust, C++ (GCC 16) y Java instalados sin
  tocar el sistema; taller Python con lint y análisis de dependencias;
- galaxia operativa con nodos reales (capacidades) y estado pendiente/ok/error;
- panel operativo: permisos pendientes con aprobar/rechazar, plan editable,
  entregables verificados y deshacer seguro del workspace;
- verificación visual automática de imágenes, vídeo y capturas de interfaz
  (detección de ventanas en negro, sin contraste o con bordes uniformes);
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
