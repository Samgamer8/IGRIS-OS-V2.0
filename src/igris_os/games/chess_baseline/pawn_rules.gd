extends RefCounted

func is_valid_pawn_move(board, side, from_x, from_y, to_x, to_y) -> bool:
    if min(from_x, from_y, to_x, to_y) < 0 or max(from_x, from_y, to_x, to_y) > 7:
        return false
    var direction = 1 if side == "white" else -1
    var start_row = 1 if side == "white" else 6
    var dx = to_x - from_x
    var dy = to_y - from_y
    var target = board[to_y][to_x]
    if dx == 0 and target == null:
        if dy == direction:
            return true
        return from_y == start_row and dy == 2 * direction and board[from_y + direction][from_x] == null
    return abs(dx) == 1 and dy == direction and target is Dictionary and target.side != side
