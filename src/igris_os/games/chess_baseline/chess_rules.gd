extends RefCounted
# Piece geometry facade. ChessGame adds king safety, castling and en passant.
const Pawn = preload("res://pawn_rules.gd")
const Sliding = preload("res://sliding_rules.gd")
const Jump = preload("res://jump_rules.gd")
var pawn = Pawn.new()
var sliding = Sliding.new()
var jump = Jump.new()

func is_valid_move(board, side, fx, fy, tx, ty) -> bool:
    if min(fx, fy, tx, ty) < 0 or max(fx, fy, tx, ty) > 7 or (fx == tx and fy == ty):
        return false
    var piece = board[fy][fx]
    var target = board[ty][tx]
    if not piece is Dictionary or piece.side != side:
        return false
    if target != null and (not target is Dictionary or target.side == side):
        return false
    match piece.type:
        "pawn": return pawn.is_valid_pawn_move(board, side, fx, fy, tx, ty)
        "rook": return sliding.rook(board, side, fx, fy, tx, ty)
        "bishop": return sliding.bishop(board, side, fx, fy, tx, ty)
        "queen": return sliding.queen(board, side, fx, fy, tx, ty)
        "knight": return jump.is_valid_knight_move(board, side, fx, fy, tx, ty)
        "king": return jump.is_valid_king_move(board, side, fx, fy, tx, ty)
    return false
