extends RefCounted

func is_path_clear(board, from_x, from_y, to_x, to_y) -> bool:
    var dx = to_x - from_x
    var dy = to_y - from_y
    if dx == 0 and dy == 0:
        return false
    if dx != 0 and dy != 0 and abs(dx) != abs(dy):
        return false
    var step_x = int(sign(dx))
    var step_y = int(sign(dy))
    var x = from_x + step_x
    var y = from_y + step_y
    while x != to_x or y != to_y:
        if x < 0 or x > 7 or y < 0 or y > 7 or board[y][x] != null:
            return false
        x += step_x
        y += step_y
    return true

func rook(board, _side, fx, fy, tx, ty) -> bool:
    return (fx == tx or fy == ty) and is_path_clear(board, fx, fy, tx, ty)

func bishop(board, _side, fx, fy, tx, ty) -> bool:
    return abs(tx - fx) == abs(ty - fy) and is_path_clear(board, fx, fy, tx, ty)

func queen(board, side, fx, fy, tx, ty) -> bool:
    return rook(board, side, fx, fy, tx, ty) or bishop(board, side, fx, fy, tx, ty)
