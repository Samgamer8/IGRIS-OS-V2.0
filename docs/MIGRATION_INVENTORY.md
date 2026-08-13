# Inventario de migracion

Cada elemento antiguo debe quedar clasificado como `migrar`, `reescribir`,
`archivar` o `descartar`. Nada se elimina antes de una validacion final y la
autorizacion expresa del propietario.

## Fuentes principales

| Fuente | Valor principal | Estrategia inicial |
|---|---|---|
| `prollecto IGRIS OS` | motores, voz, memoria, laboratorio y panel militar | extraer comportamientos con pruebas; no copiar archivos gigantes |
| `IGRIS OS` | Git, runtime limpio, releases, seguridad, SBOM y licencias | reutilizar patrones e importar modulos tras revisar cambios locales |
| versiones antiguas | prototipos y posibles recursos unicos | comparar hashes y rescatar solo elementos no presentes |

## Primer lote aceptado

- Contrato de capacidad y resultado inspirado en `igris_core/vnext`.
- Politica central de riesgo reforzada: toda escritura requiere confirmacion.
- Aislamiento logico por workspace de mision.
- Auditoria minima sin objetivo, payload ni secretos.
- Diagnostico del sistema estrictamente de solo lectura.

## Siguiente lote

1. Inventario automatizado con hash de todas las fuentes IGRIS.
2. Adaptadores de modelos locales y registro de proveedores.
3. Director de misiones y planes verificables.
4. Migracion del analisis de archivos.
5. Primer vertical completo de programacion Python.
6. Panel principal basado en la referencia militar, conectado a estado real.

