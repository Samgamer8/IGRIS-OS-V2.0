"""Fixed board storage contract shared by the sequential chess components.

This is infrastructure, not a complete rules engine or an LLM-generated game.
The developer must compile it and run its contract checks in the target Godot.
"""

CHESS_STATE_SOURCE = '''class_name ChessState
extends RefCounted

const BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"]
var board: Array = []
var current_turn: String = "white"

func _init() -> void:
    setup_board()

func setup_board() -> void:
    board = []
    current_turn = "white"
    for y in range(8):
        var row: Array = []
        for x in range(8):
            row.append(null)
        board.append(row)
    for x in range(8):
        board[0][x] = {"type": BACK_RANK[x], "side": "white"}
        board[1][x] = {"type": "pawn", "side": "white"}
        board[6][x] = {"type": "pawn", "side": "black"}
        board[7][x] = {"type": BACK_RANK[x], "side": "black"}

func get_piece(x: int, y: int):
    if not _inside(x, y):
        return null
    return board[y][x]

func move_piece(from_x: int, from_y: int, to_x: int, to_y: int) -> bool:
    # The rules component checks legality before calling this storage operation.
    if not _inside(from_x, from_y) or not _inside(to_x, to_y):
        return false
    if from_x == to_x and from_y == to_y:
        return false
    var piece = board[from_y][from_x]
    if piece == null:
        return false
    board[to_y][to_x] = piece
    board[from_y][from_x] = null
    switch_turn()
    return true

func switch_turn() -> void:
    current_turn = "black" if current_turn == "white" else "white"

func _inside(x: int, y: int) -> bool:
    return x >= 0 and x < 8 and y >= 0 and y < 8
'''
