# Igris Chees — Marfil / Obsidiana

Abre **JUGAR.cmd**. Usa la exportación nueva si IGRIS la verificó, o el Godot que comprobó el código fuente. También puedes importar `project.godot` en Godot y pulsar F6/F5.

- Clic sobre una pieza y después sobre una casilla iluminada para moverla.
- Botón derecho y movimiento del ratón para girar la cámara; rueda para acercar.
- Desactiva «Rival automático» para jugar dos personas en el mismo equipo.
- El rival automático es básico. No utiliza Ollama ni pretende tener nivel experto.
- Incluye cambio de turno, jaque y mate, ahogado, enroque, captura al paso y elección de promoción. Permite reclamar tablas por triple repetición o 50 movimientos en la posición actual. También reconoce quíntuple repetición, 75 movimientos y los casos comunes de material insuficiente.
- Los combates usan movimientos y golpes de las figuras, caída de la pieza y un destello arcano. Las piezas son modelos geométricos originales y las animaciones son sencillas.
- «Guardar partida» conserva los movimientos en los datos de usuario de Godot; «Cargar partida» los verifica antes de recuperar la posición. «Deshacer» recupera la jugada anterior o el turno completo si se juega contra el rival automático.

Se trata de una base jugable reutilizable de IGRIS. Su construcción no necesita generar código con un modelo. La aprobación del aspecto medieval y de las animaciones corresponde al usuario. No reproduce los modelos ni las animaciones de un título comercial.

Las pruebas se encuentran en `verify_game.gd` y sus resultados locales en `IGRIS_VERIFICATION.json`. Las reglas geométricas y el estado de partida están separados de la presentación y el controlador.
