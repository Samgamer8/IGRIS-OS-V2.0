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
  C++ y Java con verificación de herramientas locales; Go verificado con gofmt.
- Adjuntos: análisis, imagen, extracción de audio, miniatura y transcodificación.
- Pipeline multimedia encadenado con previsualización, evidencia y rollback.
- Mapa profundo de repositorios con búsqueda contextual y límites de lectura.
- Copia y edición aisladas de repositorios con diff, verificación y rollback.
- Cola persistente recuperable y memoria técnica de entregas verificadas.
- Progreso monotónico y cancelación cooperativa en puntos seguros.
- Coordinación de especialistas con revisión cruzada y evidencia persistente.
- Evolución con puertas de tests, seguridad y mejora; solo pasa a revisión.
- Godot: plantillas top-down, arcade y plataformas, confinadas y verificadas.

## Última entrega verificada

- Pruebas: 120 aprobadas.
- Release check: aprobado.
- Progreso granular conectado a operaciones largas: análisis y copia de repositorios,
  inventario de fuentes, pipeline multimedia, coordinación de especialistas y
  desarrollo multilingüe; propagado por el kernel y mostrado en el panel y CLI.
- Go incorporado como lenguaje verificable (gofmt -e) y enrutable por el router.
- Corrección de entorno: pytest redirigido a un `basetemp` escribible (la carpeta
  `pytest-of-samva` quedó con ACL corrupta por el sandbox y bloqueaba 69 pruebas).
- SHA-256 portable anterior: `B5CEA2379AC1D4BDE6D8BAD8CCBF32416E6E4665570AB695FC6C57DD6FAFED11`.

## Prioridades siguientes

1. Conectar indicadores de progreso granular a todas las operaciones largas. [HECHO]
2. Aislar toolchains para pruebas multilenguaje sin riesgo: Go verificado (gofmt),
   Node presente; faltan TypeScript (tsc), Rust (rustc), C++ (g++), Java (javac).
3. Ejecutar pruebas reales del motor Godot cuando esté instalado.
4. Evolucionar búsqueda contextual hacia recuperación semántica local.

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
