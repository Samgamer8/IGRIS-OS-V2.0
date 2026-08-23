# Auditoria cruzada de versiones IGRIS

Fecha: 2026-08-22

## Resultado ejecutivo

V4 es la base recomendada para continuar. V3 es la referencia estable actual.
V2 contiene regresiones de importacion y no debe ser usada como base de runtime.
Las fuentes historicas se conservan hasta una aprobacion explicita de borrado.

## Matriz de validacion

| Fuente | Tamano aproximado | Tests | Compile | Release | Health | Resultado |
|---|---:|---:|---|---|---|---|
| IGRIS OS V2.O | 4.7 GB | 62 archivos / 364 funciones | OK | OK | OK | Falla al recopilar `tests/test_context.py` |
| IGRIS OS V 3.0 | 3.9 GB | 69 archivos / 460 funciones | OK | OK | OK | Suite completa aprobada |
| IGRIS OS v4.0 | 11.9 MB limpia | 69 archivos / 460 funciones | OK | OK | OK | Checks focalizados aprobados; suite completa se bloquea tras 46% |
| V2.O.worktrees | 24.5 MB | No ejecutado | No ejecutado | No ejecutado | No ejecutado | Requiere inspeccion separada |
| IGRIS_Archivo | 1.65 GB | No ejecutado | No ejecutado | No ejecutado | No ejecutado | Archivo historico, no runtime |

## Fallo confirmado de V2

`tests/test_context.py` importa `ContextEngine` desde `igris_os.context`, pero
la version V2 no exporta ese simbolo. La coleccion se detiene antes de ejecutar
la suite completa.

## Bloqueo confirmado de V4

La suite integral avanza hasta aproximadamente 46% y queda detenida en una
operacion de socket. Las pruebas aisladas de entrada, bootstrap, contratos,
subprocessos de IA, E2E y sandbox pasan. La distribucion portable queda
bloqueada hasta hacer determinista el cierre de sockets/procesos o aislar el
test responsable.

## Fuentes de V4

- Base de codigo: `IGRIS OS V 3.0`
- Componentes historicos consultados: `IGRIS OS V2.O`, `IGRIS OS V2.O.worktrees`, `IGRIS_Archivo`
- Herramienta de distribucion adaptada como pipeline: `build_portable.ps1`

## Candidatos de limpieza futura

### Bajo riesgo, tras confirmar que no hay procesos activos

- `__pycache__/`
- `.pytest_cache/`
- `.coverage`
- logs y bases de datos generados dentro de `runtime/`

### Riesgo medio, requiere copia de seguridad

- builds y carpetas `dist/` heredadas
- worktrees sin cambios unicos
- prototipos duplicados ya cubiertos por V4

### Alto riesgo, no eliminar automaticamente

- `IGRIS OS V 3.0`
- `IGRIS OS V2.O`
- `IGRIS_Archivo`
- recursos, modelos o configuraciones cuyo uso no este demostrado

Ningun elemento de estas listas ha sido eliminado durante esta auditoria.
