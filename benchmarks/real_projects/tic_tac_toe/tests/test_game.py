from tic_tac_toe import Game


def test_x_wins_complete_match():
    game = Game()
    for move in (1, 4, 2, 5, 3):
        game.play(move)
    assert game.winner == "X"
    assert not game.draw


def test_draw_complete_match():
    game = Game()
    for move in (1, 2, 3, 5, 4, 6, 8, 7, 9):
        game.play(move)
    assert game.winner is None
    assert game.draw


def test_rejects_invalid_and_occupied_positions():
    game = Game()
    for invalid in (0, 10):
        try:
            game.play(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Debió rechazar la posición")
    game.play(1)
    try:
        game.play(1)
    except ValueError as exc:
        assert "ocupada" in str(exc)
    else:
        raise AssertionError("Debió rechazar la casilla ocupada")
