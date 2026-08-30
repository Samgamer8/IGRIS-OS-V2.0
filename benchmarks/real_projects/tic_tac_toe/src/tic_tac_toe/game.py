from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Game:
    board: list[str] = field(default_factory=lambda: [" "] * 9)
    turn: str = "X"

    def play(self, position: int) -> None:
        if self.winner or self.draw:
            raise RuntimeError("La partida ya terminó")
        if position not in range(1, 10):
            raise ValueError("La posición debe estar entre 1 y 9")
        index = position - 1
        if self.board[index] != " ":
            raise ValueError("La casilla ya está ocupada")
        self.board[index] = self.turn
        if not self.winner:
            self.turn = "O" if self.turn == "X" else "X"

    @property
    def winner(self) -> str | None:
        lines = ((0, 1, 2), (3, 4, 5), (6, 7, 8),
                 (0, 3, 6), (1, 4, 7), (2, 5, 8),
                 (0, 4, 8), (2, 4, 6))
        for a, b, c in lines:
            if self.board[a] != " " and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    @property
    def draw(self) -> bool:
        return self.winner is None and " " not in self.board

    def render(self) -> str:
        cells = [value if value != " " else str(index + 1)
                 for index, value in enumerate(self.board)]
        return "\n---+---+---\n".join(
            " " + " | ".join(cells[row:row + 3]) for row in (0, 3, 6))
