# Continuidad de IGRIS OS V2.O

## Fuente canónica

Trabajar exclusivamente en `C:\Users\samva\OneDrive\Escritorio\IGRIS OS V2.O`.
Las demás carpetas IGRIS son fuentes históricas y no deben borrarse ni mezclarse
sin inventario, pruebas y autorización expresa.

## Secuencia de trabajo obligatoria

1. Leer `PROJECT_STATE.json`, `README.md`, `docs/ARCHITECTURE.md` y este archivo.
2. Ejecutar `git status --short` y preservar cambios ajenos.
3. Ejecutar `python tools/quality_gate.py` antes de modificar.
4. Hacer cambios pequeños con pruebas de éxito, error y seguridad.
5. No afirmar que una acción se ejecutó sin evidencia real.
6. Exigir confirmación para escrituras y bloquear acciones destructivas.
7. Ejecutar nuevamente la puerta de calidad.
8. Crear un commit local descriptivo.
9. Para entregar: ejecutar `build_portable.ps1`, probar el EXE y registrar evidencia.

## Estado funcional

- Panel militar cinematográfico conectado al núcleo.
- Chat local con Ollama y selección de modelo por especialidad.
- Memoria SQLite verificada y contexto limitado.
- Programación Python con pruebas y reparación; JavaScript, TypeScript, Rust,
  C++ y Java con verificación de herramientas locales.
- Adjuntos: análisis, imagen, extracción de audio, miniatura y transcodificación.
- Godot: creación confinada de proyecto base.
- Voz y dictado locales; voz preferida Microsoft Pablo (español masculino).
- Auditoría JSONL, workspaces por misión y política central de permisos.
- Evolución: candidatos medidos, sin autopromoción directa a producción.

## Prioridades siguientes

1. Sustituir el proyecto Godot mínimo por plantillas jugables verificadas.
2. Añadir edición multimedia mediante planes encadenados, previsualización y rollback.
3. Mejorar generación multilenguaje con pruebas específicas de cada ecosistema.
4. Incorporar búsqueda semántica local sobre archivos autorizados.
5. Añadir cancelación, progreso y cola de misiones largas en el panel.

## Prompt para continuar en otra sesión

```text
Continúa IGRIS OS V2.O desde la carpeta canónica
C:\Users\samva\OneDrive\Escritorio\IGRIS OS V2.O.
Lee completos PROJECT_STATE.json, README.md, docs/ARCHITECTURE.md y
docs/SESSION_CONTINUITY.md. Comprueba git status y ejecuta
python tools/quality_gate.py antes de tocar código. Conserva la interfaz militar,
la política de permisos, el aislamiento por misión y todas las pruebas existentes.
No borres versiones antiguas ni inventes resultados. Elige la primera prioridad
pendiente, impleméntala con pruebas, valida el portable y actualiza este documento
con evidencia y próximos pasos.
```
