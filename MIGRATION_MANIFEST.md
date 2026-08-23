# IGRIS OS v4.0 - Manifiesto de migracion

## Estado

- Destino: `IGRIS OS v4.0`
- Fuente primaria: `IGRIS OS V 3.0`
- Estado: base selectiva migrada y validada
- Regla: las fuentes antiguas permanecen intactas hasta completar la validacion

## Componentes migrados

- `src/`: runtime canonico y modulos de produccion
- `tests/`: pruebas unitarias, integracion, seguridad y E2E
- `tools/`: quality gate y release check
- `assets/`: recursos del panel
- `docs/`: arquitectura y continuidad
- `main.py`, `conftest.py`, `pyproject.toml`, `README.md`, `SECURITY.md`

## Componentes excluidos deliberadamente

- `.git/`: historial y metadatos de la fuente
- `runtime/`: logs, bases de datos y estado generado
- `__pycache__/`, `.pytest_cache/`: caches locales
- `.coverage`: resultado de ejecuciones locales
- `dist/`, `build/`: artefactos de distribucion heredados
- `.venv/`, `.voice_env/`: entornos virtuales no portables
- secretos, archivos `.env`, modelos y datos generados

## Fuentes historicas pendientes de auditoria

- `IGRIS OS V2.O`
- `IGRIS OS V2.O.worktrees`
- `IGRIS_Archivo`

No eliminar ninguna fuente hasta comparar comportamiento, dependencias,
pruebas y distribucion portable contra V4.
