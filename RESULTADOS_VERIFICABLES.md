# Primer encargo grafico verificable

IGRIS puede dibujar una o dos esferas neuronales mediante la capacidad
`image.neural_sphere`. No es un modelo generativo ni reproduce un fotograma
de una pelicula. El resultado es una ilustracion programatica local.

## Probar desde el panel

Reinicie IGRIS cuando no haya trabajos ejecutandose y escriba:

> Crea una imagen de dos esferas neuronales, como una visualizacion de pensamiento.

Si hay un encargo diferente pendiente, IGRIS pregunta si debe dejarlo
pendiente o continuar con el. Despues pide permiso para escribir la imagen.
La salida queda en `runtime/missions/<id>/output/` y se muestra en el chat,
junto con el metodo y el informe de comprobacion. No modifica el ajedrez,
no descarga modelos y no necesita la GPU para este dibujo.

La cola conserva el artefacto al reiniciar. El informe contiene dimensiones,
SHA256 y comprobacion de contenido visible por region de esfera; no certifica
calidad artistica ni que cualquier otra peticion de imagen pueda resolverse.

## Evidencia

`runtime/acceptance/neural-image/acceptance_result.json` contiene la ejecucion
de la peticion original con router, autorizacion, kernel y cola aislados.
Las pruebas incluyen el panel Qt hasta la creacion y presentacion del PNG,
rechazo de campos no permitidos, permisos, una/dos esferas y recuperacion.
La cola real de proyectos anteriores no se utiliza para estas comprobaciones.

Esto demuestra una capacidad concreta, no un agente general ya terminado.