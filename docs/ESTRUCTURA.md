# IGRIS OS V2.0 — Catálogo de la estructura

Copia canónica, limpia y revisada. Sin builds, cachés, runtime del usuario
ni binarios voluminosos (salvo el Godot portable en `.tools/`).

```
prollecto IGRIS V 2.0 REMASTERIZADO/
├─ main.py                  # Punto de entrada unificado (panel o CLI)
├─ launch_igris.ps1         # Lanzador PowerShell
├─ pyproject.toml           # Metadatos y dependencias
├─ README.md                # Visión y estado del sistema
├─ SECURITY.md              # Modelo de seguridad
├─ .gitignore               # Exclusión de datos privados y artefactos
├─ .tools/
│  └─ godot/                # Godot 4.7.1 portable (pipeline de juegos)
├─ src/igris_os/
│  ├─ application/          # Kernel, director, router, cola, aprobación, workflow
│  ├─ ai/                   # Proveedores Ollama y enrutado por dificultad/presupuesto
│  ├─ capabilities/         # Catálogo de capacidades y creación de proyectos
│  ├─ domain/               # Contratos: Mission, ExecutionResult, etc.
│  ├─ evaluation/           # Verificador independiente de entregas
│  ├─ evolution/            # Laboratorio de evolución en cuarentena
│  ├─ files/                # Análisis de repositorios y staging
│  ├─ games/                # Godot: scaffold, playtest, export a .exe
│  ├─ memory/               # Memoria SQLite verificada y compresor
│  ├─ models.py             # Modelos de dominio compartidos
│  ├─ multimedia/           # Pipeline imagen/vídeo/audio + verificación visual
│  ├─ programming/          # Taller Python, multi-lenguaje, repos, parches
│  ├─ retrieval/            # Contexto de repositorios y watcher
│  ├─ security/             # Sandbox (PEP 578), política, permisos
│  ├─ storage/              # Workspace aislado y auditoría JSONL
│  ├─ tools/                # Catálogo de herramientas, cadenas, devops, Git
│  ├─ ui/                   # Panel PyQt6 (galaxia, permisos, entregables, deshacer)
│  └─ voice/                # Voz Windows (Pablo) y dictado local
├─ tests/                   # Unit, integración, penetración y seguridad
├─ tools/                   # release_check, quality_gate y utilidades de CI
├─ docs/                    # Arquitectura, migración y validación
└─ assets/                  # Recursos del panel (estética, audio)
```

## Límites de esta copia

- `runtime/` y `generated/` se crean al ejecutar (logs, misiones, memoria,
  informes) y **no** se versionan.
- Los compiladores portátiles (Rust/JDK/GCC) residen en `.tools/` de la fuente
  original y se resuelven por PATH; para reproducirlos, ver
  `tools/setup_portable.ps1` o la documentación de instalación.
- La garantía dura de aislamiento (AppContainer/contenedor de Windows) se añade
  sobre el sandbox Python ya existente cuando se despliegue en producción.
