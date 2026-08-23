# Limpieza ejecutada

Fecha: 2026-08-22

Se eliminaron residuos de distribución y entornos antiguos que V4 no utiliza:

- `IGRIS OS V2.O/.tools`
- `IGRIS OS V2.O/build`
- `IGRIS OS V2.O/dist`
- `IGRIS OS V2.O/.venv`
- `IGRIS OS V2.O/.voice_env`
- `IGRIS OS V 3.0/.tools`
- caches y cobertura regenerables de V2, V3 y V4
- resultados de selftest y capturas temporales dentro de `IGRIS OS V2.O/runtime`

Se conservaron deliberadamente:

- código fuente y pruebas de V2 y V3;
- documentación;
- `runtime` y sus datos;
- `IGRIS_Archivo`;
- `IGRIS OS V2.O/runtime/voice_dataset`;
- recursos y configuraciones no comparados;
- repositorios Git.

Tambien se eliminaron 352 archivos duplicados exactos, comparados por SHA-256
contra V4, dentro de `src` y `tests` de V2 y V3. Permanecen protegidos:

- V3: 9 archivos de codigo y 5 pruebas unicas.
- V2: 30 archivos de codigo y 9 pruebas unicas.

Revision posterior: los dos worktrees experimentales fueron comparados por
contenido y eliminados por ser snapshots obsoletos sin capacidades verificadas.
V3 quedo sin archivos; Windows mantiene bloqueado su directorio contenedor.
`IGRIS_Archivo` permanece intacto.

Motivo: estos elementos conservados pueden contener código, datos o material
histórico único. Se revisarán antes de cualquier eliminación posterior.
