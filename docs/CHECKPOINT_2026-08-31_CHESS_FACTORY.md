# Punto de control: IGRIS Original Chess 3D

Fecha: 2026-08-31 (Europe/Madrid)

## Objetivo que no debe reducirse

Mejorar IGRIS OS para que planifique, genere por componentes, pruebe, repare y
valide autonomamente un juego original de ajedrez 3D inspirado en la categoria
visual de finales de los anos 90, sin copiar codigo ni recursos protegidos, y
entregar un prototipo jugable verificable.

## Ubicaciones autoritativas

- Repositorio: C:\Users\samva\OneDrive\Escritorio\IGRIS OS V 5
- Juego: proyectos\remaster_evaluation\IGRIS_Original_Chess_3D
- Orquestador: src\igris_os\games\sequential_developer.py
- Runtime: src\igris_os\games\runtime.py
- Pruebas: tests\test_sequential_game_developer.py

## Arquitectura que debe conservarse

1. IGRIS recibe el objetivo y conserva la aprobacion final.
2. El juego se divide en microcomponentes con dependencias explicitas.
3. Dos especialistas locales proponen candidatos por ronda.
4. Validacion estatica, compilacion Godot y pruebas runtime rechazan candidatos.
5. Solo el microcomponente rechazado vuelve a su cola.
6. No se aceptan falsos positivos, recursos externos ni codigo protegido.
7. El producto completo debe arrancar, ser jugable, medirse y exportarse.

## Evidencia aceptada

Cada pieza fue instanciada en Godot 4.7.2 mediante un arnes independiente:

| Componente | Resultado | Mallas |
|---|---:|---:|
| pawn_visual.gd | OK, retorno 0 | 6 |
| rook_visual.gd | OK, retorno 0 | 8 |
| knight_visual.gd | OK, retorno 0 | 6 |
| bishop_visual.gd | OK, retorno 0 | 5 |
| queen_visual.gd | OK, retorno 0 | 8 |
| king_visual.gd | OK, retorno 0 | 7 |

piece_factory.gd fue generado y compila, pero falta un arnes que cree las seis
piezas para ambos bandos en una sola ejecucion.

Ultima suite ejecutada antes de la modificacion final del arnes logico:

    python -m pytest -q tests\test_sequential_game_developer.py tests\test_runtime_probe.py tests\test_inventory.py
    27 passed

Importante: despues se conectaron pruebas runtime especificas por microcomponente
logico. Esos ultimos cambios aun no se han vuelto a probar.

## Estado exacto del nucleo logico

La ultima ejecucion termino de forma controlada y no queda generador activo.
Genero nuevas versiones de chess_state.gd, pawn_rules.gd, sliding_rules.gd y
jump_rules.gd, pero el arnes integral probo que no son funcionalmente validas:

- chess_state.gd: peones en filas incorrectas y contrato fila/columna incompatible.
- pawn_rules.gd: constructor con bando y casillas null tratadas como diccionarios.
- sliding_rules.gd: la diagonal incluye la casilla destino en el camino.
- jump_rules.gd: el rey acepta un desplazamiento de cero casillas.
- chess_rules.gd: no aceptado; ultimo fallo IGRIS_RULE_FAILED:piece_dictionary.

El orquestador ya llama _smoke_logic(project, path) para cada uno de los cinco
componentes. Al reanudar, deben rechazarse y regenerarse individualmente. No
repararlos a mano ni aceptarlos solo porque compilen.

## Estado del tablero e integracion

- board_view.gd, camera_controller.gd, game_controller.gd y main.gd son versiones
  antiguas no aceptadas funcionalmente.
- El tablero antiguo mezcla reglas, turnos, camara, iluminacion e input.
- El controlador antiguo contiene APIs de Godot 3 y nodos inexistentes.
- Regenerarlos solo despues de que el arnes integral imprima IGRIS_RULE_SMOKE_OK.

## Siguiente accion exacta

1. Ejecutar primero:

    $env:PYTHONPATH='src'
    python -m pytest -q tests\test_sequential_game_developer.py tests\test_runtime_probe.py tests\test_inventory.py

2. Corregir pruebas o mocks sin rebajar el contrato funcional.
3. Reanudar develop_chess_3d con resume=True y
   igris_os.ai.ollama.OllamaClient; no usar igris_os.core.ollama_client.
4. Exigir pruebas individuales y luego el arnes integral de chess_rules.gd.
5. Despues regenerar tablero, camara, controlador y principal.

## Precauciones de continuidad

- Git contiene numerosos cambios previos/no relacionados. No hacer reset,
  checkout, limpieza masiva ni commit global.
- No borrar ni regenerar las seis piezas visuales ya verificadas.
- No copiar activos de referencia ni DLL/DirectX antiguos.
- Los scripts URES pertenecen a otro proyecto y no deben entrar en el ajedrez.
- La ampliacion de source_inventory.py se hizo antes de esa aclaracion; queda
  pendiente decidir si conservarla o revertir solo ese cambio.

## Condicion final aun no cumplida

Reglas completas, 64 casillas y 32 piezas visibles, seleccion y movimientos
legales, capturas y turnos, camara fluida, menu moderno original, arranque real,
evidencia visual, rendimiento medido y exportacion Windows reproducible.
