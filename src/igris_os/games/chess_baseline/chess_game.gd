extends RefCounted
const State = preload("res://chess_state.gd")
const Rules = preload("res://chess_rules.gd")
const PROMOTIONS = ["queen", "rook", "bishop", "knight"]
const SYMBOLS = {"pawn": "p", "rook": "r", "knight": "n", "bishop": "b", "queen": "q", "king": "k"}
var rules = Rules.new()
var position: Dictionary = {}
var history: Array = []
var notation: Array = []
var repetitions: Dictionary = {}
var claimed_draw = false

func _init():
    reset()

func reset():
    var state = State.new()
    position = {"board": state.board, "side": "white", "castling": "KQkq", "ep": Vector2i(-1, -1), "halfmove": 0, "fullmove": 1}
    history = []
    notation = []
    repetitions = {position_key(position): 1}
    claimed_draw = false

func opposite(side):
    return "black" if side == "white" else "white"

func in_check(p: Dictionary, side: String) -> bool:
    for y in range(8):
        for x in range(8):
            var piece = p.board[y][x]
            if piece != null and piece.type == "king" and piece.side == side:
                return attacked(p.board, x, y, opposite(side))
    return true

func attacked(board, tx, ty, by_side) -> bool:
    for y in range(8):
        for x in range(8):
            var piece = board[y][x]
            if piece == null or piece.side != by_side:
                continue
            var dx = abs(tx - x)
            var dy = ty - y
            if piece.type == "pawn":
                if dx == 1 and dy == (1 if by_side == "white" else -1):
                    return true
            elif piece.type == "king":
                if max(dx, abs(dy)) == 1:
                    return true
            elif piece.type == "knight":
                if rules.jump.is_knight_move(board, by_side, x, y, tx, ty):
                    return true
            elif piece.type == "rook" and rules.sliding.rook(board, by_side, x, y, tx, ty):
                return true
            elif piece.type == "bishop" and rules.sliding.bishop(board, by_side, x, y, tx, ty):
                return true
            elif piece.type == "queen" and rules.sliding.queen(board, by_side, x, y, tx, ty):
                return true
    return false

func castle_allowed(p, fx, fy, tx, ty) -> bool:
    var row = 0 if p.side == "white" else 7
    if fx != 4 or fy != row or ty != row or tx not in [2, 6]:
        return false
    var right = ("K" if tx == 6 else "Q") if p.side == "white" else ("k" if tx == 6 else "q")
    if not p.castling.contains(right) or in_check(p, p.side):
        return false
    var rook_x = 7 if tx == 6 else 0
    var rook = p.board[row][rook_x]
    if rook == null or rook.type != "rook" or rook.side != p.side:
        return false
    for x in (range(5, 7) if tx == 6 else range(1, 4)):
        if p.board[row][x] != null:
            return false
    var middle = 5 if tx == 6 else 3
    var board = p.board.duplicate(true)
    board[row][middle] = board[row][4]
    board[row][4] = null
    return not attacked(board, middle, row, opposite(p.side))

func is_legal(p, fx, fy, tx, ty) -> bool:
    if min(fx, fy, tx, ty) < 0 or max(fx, fy, tx, ty) > 7 or (fx == tx and fy == ty):
        return false
    var piece = p.board[fy][fx]
    var target = p.board[ty][tx]
    if piece == null or piece.side != p.side:
        return false
    if target != null and (target.side == p.side or target.type == "king"):
        return false
    var valid = rules.is_valid_move(p.board, p.side, fx, fy, tx, ty)
    if piece.type == "king" and abs(tx - fx) == 2:
        valid = castle_allowed(p, fx, fy, tx, ty)
    if piece.type == "pawn" and target == null and p.ep == Vector2i(tx, ty):
        var direction = 1 if p.side == "white" else -1
        var victim = p.board[fy][tx]
        valid = abs(tx - fx) == 1 and ty - fy == direction and victim != null and victim.type == "pawn" and victim.side != p.side
    if not valid:
        return false
    return not in_check(apply_unchecked(p, {"fx": fx, "fy": fy, "tx": tx, "ty": ty, "promotion": "queen"}), p.side)

func legal_moves(p: Dictionary = {}) -> Array:
    if p.is_empty():
        p = position
    var result: Array = []
    for fy in range(8):
        for fx in range(8):
            var piece = p.board[fy][fx]
            if piece == null or piece.side != p.side:
                continue
            for ty in range(8):
                for tx in range(8):
                    if is_legal(p, fx, fy, tx, ty):
                        var choices = PROMOTIONS if piece.type == "pawn" and ty in [0, 7] else [""]
                        for promotion in choices:
                            result.append({"fx": fx, "fy": fy, "tx": tx, "ty": ty, "promotion": promotion})
    return result

func apply_unchecked(p, move) -> Dictionary:
    var next = p.duplicate(true)
    var board = next.board
    var fx = move.fx
    var fy = move.fy
    var tx = move.tx
    var ty = move.ty
    var piece = board[fy][fx]
    var target = board[ty][tx]
    var capture = target != null
    var pawn_move = piece.type == "pawn"
    if pawn_move and tx != fx and target == null:
        board[fy][tx] = null
        capture = true
    board[ty][tx] = piece
    board[fy][fx] = null
    if piece.type == "king":
        next.castling = next.castling.replace("K", "").replace("Q", "") if p.side == "white" else next.castling.replace("k", "").replace("q", "")
        if abs(tx - fx) == 2:
            var rook_x = 7 if tx > fx else 0
            var rook_to = 5 if tx > fx else 3
            board[fy][rook_to] = board[fy][rook_x]
            board[fy][rook_x] = null
    for corner in [{"x":0,"y":0,"right":"Q"},{"x":7,"y":0,"right":"K"},{"x":0,"y":7,"right":"q"},{"x":7,"y":7,"right":"k"}]:
        if (fx == corner.x and fy == corner.y) or (tx == corner.x and ty == corner.y):
            next.castling = next.castling.replace(corner.right, "")
    if pawn_move and ty in [0, 7]:
        piece.type = move.promotion if move.get("promotion", "") in PROMOTIONS else "queen"
    next.ep = Vector2i(fx, (fy + ty) / 2) if pawn_move and abs(ty - fy) == 2 else Vector2i(-1, -1)
    next.halfmove = 0 if pawn_move or capture else p.halfmove + 1
    next.fullmove = p.fullmove + (1 if p.side == "black" else 0)
    next.side = opposite(p.side)
    return next

func play(fx, fy, tx, ty, promotion = "queen") -> bool:
    if claimed_draw or status().terminal or not is_legal(position, fx, fy, tx, ty):
        return false
    var piece = position.board[fy][fx]
    if piece.type == "pawn" and ty in [0, 7] and promotion not in PROMOTIONS:
        return false
    var move = {"fx":fx,"fy":fy,"tx":tx,"ty":ty,"promotion":promotion}
    history.append(position.duplicate(true))
    notation.append(square_name(fx, fy) + square_name(tx, ty) + (SYMBOLS[promotion] if piece.type == "pawn" and ty in [0, 7] else ""))
    position = apply_unchecked(position, move)
    var key = position_key(position)
    repetitions[key] = repetitions.get(key, 0) + 1
    return true

func undo() -> bool:
    if history.is_empty():
        return false
    var key = position_key(position)
    repetitions[key] -= 1
    position = history.pop_back()
    notation.pop_back()
    claimed_draw = false
    return true

func position_key(p) -> String:
    var parts = to_fen(p).split(" ")
    var usable_ep = false
    if p.ep.x >= 0:
        var fy = p.ep.y - (1 if p.side == "white" else -1)
        for fx in [p.ep.x - 1, p.ep.x + 1]:
            if fx >= 0 and fx < 8 and fy >= 0 and fy < 8:
                var pawn = p.board[fy][fx]
                if pawn != null and pawn.type == "pawn" and pawn.side == p.side and is_legal(p, fx, fy, p.ep.x, p.ep.y):
                    usable_ep = true
    return "%s %s %s %s" % [parts[0], parts[1], parts[2], parts[3] if usable_ep else "-"]

func insufficient_material(p) -> bool:
    var minors: Array = []
    for y in range(8):
        for x in range(8):
            var piece = p.board[y][x]
            if piece == null or piece.type == "king":
                continue
            if piece.type not in ["bishop", "knight"]:
                return false
            minors.append({"type":piece.type,"color":(x + y) % 2})
    if minors.size() <= 1:
        return true
    for minor in minors:
        if minor.type != "bishop" or minor.color != minors[0].color:
            return false
    return true

func status() -> Dictionary:
    var check = in_check(position, position.side)
    var moves = legal_moves()
    var result = {"terminal":false, "check":check, "label":"Jaque" if check else "En juego", "claimable":false}
    if moves.is_empty():
        result.terminal = true
        result.label = "Jaque mate · gana " + ("Marfil" if position.side == "black" else "Obsidiana") if check else "Tablas por ahogado"
    elif claimed_draw or repetitions.get(position_key(position), 0) >= 5 or position.halfmove >= 150 or insufficient_material(position):
        result.terminal = true
        result.label = "Tablas"
    else:
        result.claimable = repetitions.get(position_key(position), 0) >= 3 or position.halfmove >= 100
    return result

func claim_draw() -> bool:
    if status().claimable:
        claimed_draw = true
        return true
    return false

func square_name(x, y):
    return "abcdefgh"[x] + str(y + 1)

func to_fen(p: Dictionary = {}) -> String:
    if p.is_empty(): p = position
    var rows: Array = []
    for y in range(7, -1, -1):
        var row = ""
        var empty = 0
        for x in range(8):
            var piece = p.board[y][x]
            if piece == null:
                empty += 1
            else:
                if empty > 0: row += str(empty); empty = 0
                var symbol = SYMBOLS[piece.type]
                row += symbol.to_upper() if piece.side == "white" else symbol
        if empty > 0: row += str(empty)
        rows.append(row)
    return "%s %s %s %s %s %s" % ["/".join(rows), "w" if p.side == "white" else "b", p.castling if p.castling != "" else "-", square_name(p.ep.x, p.ep.y) if p.ep.x >= 0 else "-", p.halfmove, p.fullmove]

func load_fen(fen: String) -> bool:
    var parts = fen.strip_edges().split(" ", false)
    if parts.size() != 6 or parts[1] not in ["w", "b"] or not parts[4].is_valid_int() or not parts[5].is_valid_int():
        return false
    var rows = parts[0].split("/")
    if rows.size() != 8: return false
    var board: Array = []
    var kings = {"white":0,"black":0}
    for row_text in rows:
        var row: Array = []
        for letter in row_text:
            if letter in "12345678":
                for n in range(int(letter)): row.append(null)
            else:
                var piece_type = SYMBOLS.find_key(letter.to_lower())
                if piece_type == null: return false
                var side = "white" if letter == letter.to_upper() else "black"
                row.append({"type":piece_type,"side":side})
                if piece_type == "king": kings[side] += 1
        if row.size() != 8: return false
        board.push_front(row)
    if kings.white != 1 or kings.black != 1: return false
    var ep = Vector2i(-1, -1)
    if parts[3] != "-":
        if parts[3].length() != 2 or parts[3][0] not in "abcdefgh" or parts[3][1] not in "36": return false
        ep = Vector2i("abcdefgh".find(parts[3][0]), int(parts[3][1]) - 1)
    var rights = parts[2].replace("-", "")
    for letter in rights:
        if letter not in "KQkq": return false
    position = {"board":board,"side":"white" if parts[1] == "w" else "black", "castling":rights,"ep":ep,"halfmove":int(parts[4]),"fullmove":int(parts[5])}
    history = []
    notation = []
    repetitions = {position_key(position):1}
    claimed_draw = false
    return true
