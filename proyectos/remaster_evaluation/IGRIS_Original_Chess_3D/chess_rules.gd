class_name ChessRules extends RefCounted

var pawn_rules = preload('res://pawn_rules.gd').new()
var sliding_rules = preload('res://sliding_rules.gd').new()
var jump_rules = preload('res://jump_rules.gd').new()

func is_valid_move(board, side, from_x, from_y, to_x, to_y):
    if board[from_y][from_x].type == 'pawn':
        return pawn_rules.is_valid_pawn_move(board, side, from_x, from_y, to_x, to_y)
    elif board[from_y][from_x].type == 'rook':
        return sliding_rules.rook(from_x, from_y, to_x, to_y, board)
    elif board[from_y][from_x].type == 'bishop':
        return sliding_rules.bishop(from_x, from_y, to_x, to_y, board)
    elif board[from_y][from_x].type == 'queen':
        return sliding_rules.queen(from_x, from_y, to_x, to_y, board)
    elif board[from_y][from_x].type == 'knight':
        return jump_rules.is_valid_knight_move(board, from_x, from_y, to_x, to_y)
    elif board[from_y][from_x].type == 'king':
        return jump_rules.is_valid_king_move(board, from_x, from_y, to_x, to_y)
    return false