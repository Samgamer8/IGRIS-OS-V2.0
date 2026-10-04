extends RefCounted

func is_knight_move(_board, _side, fx, fy, tx, ty) -> bool:
    var dx = abs(tx - fx)
    var dy = abs(ty - fy)
    return (dx == 1 and dy == 2) or (dx == 2 and dy == 1)

func is_king_move(_board, _side, fx, fy, tx, ty) -> bool:
    return max(abs(tx - fx), abs(ty - fy)) == 1

func is_valid_knight_move(board, side, fx, fy, tx, ty) -> bool:
    return is_knight_move(board, side, fx, fy, tx, ty)

func is_valid_king_move(board, side, fx, fy, tx, ty) -> bool:
    return is_king_move(board, side, fx, fy, tx, ty)
