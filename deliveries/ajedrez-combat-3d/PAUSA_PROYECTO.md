# Estado guardado para continuar

El usuario ha pedido guardar esta etapa y pasar a otra tarea urgente.
Esta entrega es un prototipo en pausa, no el juego final ni un ejecutable Windows.

## Abrir lo disponible

Ejecutar `ABRIR_JUEGO.cmd`. Requiere Node.js, que esta instalado en este equipo.
Se abre la compilacion en el navegador mediante un servidor solo de loopback,
sin cuentas ni servicios remotos. Cerrar la consola detiene el servidor.
La muestra de figuras esta en `studio.html` dentro de esa misma direccion local.

## Contenido

- `src`, `tools`, `tests`, `package.json` y `package-lock.json`: codigo y herramientas.
- `dist`: version compilada para abrir sin reinstalar dependencias.
- `public/models`: GLB y proyectos Blender de las figuras y sus revisiones.
- `model-work`: importaciones y copias de trabajo para retomar modelado.
- `evidence`: capturas y medidas de apoyo y encuadre del tablero.
- `ESTADO_TABLERO.md`: limites y comprobaciones de coherencia visual.

No se copia `node_modules` para evitar duplicar cientos de archivos de dependencias.
Para desarrollar: `npm ci`, `npm test`, `npm run test:visual`, `npm run dev`.
Las pruebas visuales actuales utilizan Microsoft Edge.

## Lo comprobado

- Motor de reglas chess.js y Stockfish local preparado.
- Modelos reales de torre y dragones integrados en el tablero.
- Cola y alas de dragon recogidas sobre copias del esqueleto, escala uniforme.
- Figuras aprobadas centradas, con margen de casilla y apoyo medido.
- Compilacion correcta, 21 pruebas unitarias y 2 pruebas de navegador en la ultima validacion.
- Jugada e2-e4 por clic y encuadre de escritorio y movil comprobados.

## Pendiente

- Aprobar el resto de figuras y reemplazar los modelos provisionales.
- Marcha articulada continua, combates entre figuras y colisiones/efectos comprobados.
- Revision artistica y rendimiento en partidas completas.
- Empaquetado y verificacion de un ejecutable Windows final.
- Verificar permisos de redistribucion de los modelos aportados antes de publicar.

Los originales de PIEZAS_AJEDREZ_SHAPR3D y los archivos anteriores de
IGRIS_CHESS_MODERN no se sobrescriben ni se eliminan.