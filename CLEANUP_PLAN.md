# Plan de depuracion IGRIS

Fecha: 2026-08-22

## Limpieza ejecutada

Se eliminaron 183 elementos inequívocamente regenerables en V2, V3 y V4:

- `__pycache__/`
- `.pytest_cache/`
- `.coverage`

No se eliminó código fuente, modelos, builds, distribuciones, runtime,
entornos virtuales ni proyectos históricos.

## Candidatos pendientes

### Requieren solo comprobación de proceso

- logs temporales antiguos
- bases de datos de pruebas
- workspaces de misiones ya finalizadas

### Requieren respaldo y comparación

- `IGRIS OS V2.O/.tools`
- `IGRIS OS V2.O/build`
- `IGRIS OS V2.O/dist`
- `IGRIS OS V2.O/runtime`
- `IGRIS OS V2.O/.venv`
- `IGRIS OS V2.O/.voice_env`
- `IGRIS OS V 3.0/.tools`

### No eliminar sin revisión explícita

- `IGRIS OS V2.O/src`
- `IGRIS OS V2.O/tests`
- `IGRIS OS V 3.0/src`
- `IGRIS OS V 3.0/tests`
- `IGRIS_Archivo`
- modelos, voces, recursos y configuraciones no clasificados

## Regla de borrado

Antes de eliminar un candidato de riesgo medio o alto:

1. comprobar que ningún proceso lo usa;
2. comparar su código contra V4;
3. identificar archivos únicos;
4. crear copia o cuarentena;
5. verificar V4 después del movimiento;
6. registrar la acción y su posibilidad de rollback.
