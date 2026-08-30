# IGRIS OS

IGRIS OS es un orquestador local para misiones asistidas, desarrollo de software, verificacion de entregas y una interfaz de escritorio. Las operaciones con efectos requieren aprobacion explicita.

## Requisitos

- Windows 10/11
- Python 3.11 o posterior
- Ollama opcional para funciones de IA local
- Godot, Node.js y otras toolchains solo para las capacidades que las necesiten

## Instalacion de desarrollo

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Uso

```powershell
python main.py health
python main.py capabilities
python main.py providers
python main.py panel
python main.py plan "Crear una API local"
```

Sin argumentos, `python main.py` abre la interfaz grafica. El comando instalado equivalente es `igris`. Las acciones que ejecutan codigo exigen `--approve-execution`.

## Validacion

Validacion rapida para desarrollo:

```powershell
python tools/quality_gate.py
```

Validacion integral antes de publicar:

```powershell
python tools/quality_gate.py --full
python tools/release_check.py
```

La suite tambien puede ejecutarse directamente con `python -m pytest -q`. Los resultados generados se escriben bajo `runtime/` y no son codigo fuente.

## Estructura

- `src/igris_os/`: paquete principal.
- `tests/`: pruebas unitarias, de integracion y de seguridad.
- `tools/`: utilidades mantenidas para calidad, voz y empaquetado.
- `benchmarks/`: proyectos pequeños usados como pruebas realistas.
- `assets/`: recursos de la interfaz.
- `docs/`: arquitectura, seguridad y manuales de usuario.

## Empaquetado

`build_portable.ps1` valida el proyecto y genera el ejecutable con PyInstaller. Los directorios `build/`, `dist/`, `runtime/`, caches y coberturas son artefactos regenerables y estan excluidos de Git.

## Seguridad

Consulta `SECURITY.md` y `AUTONOMY_POLICY.md`. No guardes credenciales, bases de datos ni modelos en el repositorio.
