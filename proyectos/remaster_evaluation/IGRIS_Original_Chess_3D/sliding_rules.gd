extends RefCounted

class_name SlidingRules

func rook(from_x, from_y, to_x, to_y, board):
    if from_x != to_x and from_y != to_y:
        return false
    return is_path_clear(from_x, from_y, to_x, to_y, board)

func bishop(from_x, from_y, to_x, to_y, board):
    if abs(from_x - to_x) != abs(from_y - to_y):
        return false
    return is_path_clear(from_x, from_y, to_x, to_y, board)

func queen(from_x, from_y, to_x, to_y, board):
    return rook(from_x, from_y, to_x, to_y, board) or bishop(from_x, from_y, to_x, to_y, board)

func is_path_clear(from_x, from_y, to_x, to_y, board):
    if from_x == to_x:
        return is_path_clear_vertical(from_x, from_y, to_y, board)
    elif from_y == to_y:
        return is_path_clear_horizontal(from_x, from_y, to_x, board)
    elif abs(from_x - to_x) == abs(from_y - to_y):
        return is_path_clear_diagonal(from_x, from_y, to_x, to_y, board)
    return false

func is_path_clear_vertical(x, y1, y2, board):
    var step = 1 if y2 > y1 else -1
    for y in range(y1 + step, y2, step):
        if board[y][x] != null:
            return false
    return true

func is_path_clear_horizontal(y, x1, x2, board):
    var step = 1 if x2 > x1 else -1
    for x in range(x1 + step, x2, step):
        if board[y][x] != null:
            return false
    return true

func is_path_clear_diagonal(x1, y1, x2, y2, board):
    var step_x = 1 if x2 > x1 else -1
    var step_y = 1 if y2 > y1 else -1
    for i in range(1, abs(x2 - x1) + 1):
        if board[y1 + step_y * i][x1 + step_x * i] != null:
            return false
    return true