from __future__ import annotations

from .game import Game


def main() -> int:
    game = Game()
    print("Tres en raya — X comienza")
    while not game.winner and not game.draw:
        print(game.render())
        try:
            game.play(int(input(f"Jugador {game.turn}, elige 1-9: ")))
        except (ValueError, RuntimeError) as exc:
            print(f"Movimiento inválido: {exc}")
    print(game.render())
    print(f"Ganó {game.winner}" if game.winner else "Empate")
    return 0
