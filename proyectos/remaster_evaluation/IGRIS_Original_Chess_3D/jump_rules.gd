extends RefCounted

func is_valid_knight_move(board, from_x, from_y, to_x, to_y):
    var dx = abs(to_x - from_x)
    var dy = abs(to_y - from_y)
    return (dx == 2 and dy == 1) or (dx == 1 and dy == 2)

func is_valid_king_move(board, from_x, from_y, to_x, to_y):
    var dx = abs(to_x - from_x)
    var dy = abs(to_y - from_y)
    return dx <= 1 and dy <= 1