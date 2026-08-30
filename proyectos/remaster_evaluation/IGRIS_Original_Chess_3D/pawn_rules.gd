class_name PawnRules extends RefCounted

var direction: int
var start_row: int

func _init(side: String):
    if side == "white":
        direction = 1
        start_row = 1
    elif side == "black":
        direction = -1
        start_row = 6

func is_valid_pawn_move(board: Array, from_row: int, from_col: int, to_row: int, to_col: int) -> bool:
    var piece = board[from_row][from_col]
    if piece["type"] != "pawn":
        return false

    var row_diff = to_row - from_row
    var col_diff = abs(to_col - from_col)

    if row_diff == 0:
        return false

    if col_diff > 1:
        return false

    if row_diff == 2:
        if from_row != start_row or col_diff != 0 or board[from_row + direction][from_col]["type"] != "empty":
            return false
    elif row_diff == 1:
        if col_diff == 0:
            if board[to_row][to_col]["type"] != "empty":
                return false
        elif col_diff == 1:
            if board[to_row][to_col]["type"] == "empty":
                return false
            if board[to_row][to_col]["side"] == piece["side"]:
                return false

    return true