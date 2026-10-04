# Coherencia de figuras y tablero

## Ajuste actual

- Casillas visuales de 1,8 unidades; las coordenadas legales siguen en chess.js.
- Dragones rojo y negro reales, con geometria y texturas aportadas por el usuario.
- Pose compacta aplicada sobre copias del esqueleto: cola recogida y alas mas verticales.
- Escalado uniforme, sin comprimir o estirar la malla por ejes.
- Altura objetivo de peones: 0,95; torre: 1,65 unidades.
- Huella maxima de figuras aprobadas: 86% de la casilla, con margen entre casillas vecinas.
- Las figuras se centran y su punto mas bajo se coloca a la altura de apoyo del tablero.
- Los peones y torres ya no reciben un salto vertical arbitrario al desplazarse.
- Camara ajustada para incluir el tablero en escritorio y pantalla vertical.

La pose compacta se usa en la partida; los GLB originales y las muestras del visor
siguen conservados. El resto de personajes aun incluye reconstrucciones provisionales.
La torre usa el modelo original importado; no se ha fingido que los otros modelos
son archivos originales recuperados.

## Verificacion

`npm test` comprueba reglas, assets, dimensiones y aplicacion no acumulativa de la pose.
`npm run test:visual` ejecuta Edge con Playwright y comprueba las figuras reales:

- Veinte instancias aprobadas: dieciseis dragones y cuatro torres.
- Margen de casilla, centramiento y apoyo de cada instancia.
- Canvas con contenido y encuadre en 1440x900 y 390x844, sin desbordamiento horizontal.
- Jugada e2-e4 por clic, con medidas de apoyo durante la transicion y casilla legal final.

Evidencia generada en `evidence/board-fit.json`, `evidence/pawn-movement.json`,
`evidence/board-1440.png` y `evidence/board-390.png`.

## Limites

Se trata de un movimiento cinematico controlado por reglas de ajedrez, no de una
simulacion de cuerpos rigidos. Las comprobaciones de limites y apoyo no prueban
anatomia perfecta ni ausencia de toda interseccion interna entre alas y cuerpo.
La marcha articulada continua, el contacto de armas, las reacciones de combate y
sus colisiones necesitan validacion especifica en la fase siguiente.
No se ha entregado todavia el ejecutable final ni se dan por aprobados los modelos restantes.