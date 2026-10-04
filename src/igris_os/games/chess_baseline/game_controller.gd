extends Node
signal changed
signal promotion_requested
const Game = preload("res://chess_game.gd")
var game = Game.new()
var board_view
var camera
var selected = Vector2i(-1,-1)
var busy = false
var bot_enabled = true
var animation_seconds = 0.65
var pending = Vector2i(-1,-1)
var message = "Selecciona una pieza de Marfil"
var generation = 0
var save_path = "user://igris_chees_save.json"

func connect_scene(board, view_camera):
    board_view = board
    camera = view_camera
    board_view.sync(game.position.board)
    changed.emit()

func _unhandled_input(event):
    if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and event.pressed:
        choose(board_view.pick(camera,event.position))

func choose(square):
    if busy or pending.x >= 0 or (bot_enabled and game.position.side == "black") or game.status().terminal:
        return
    if square.x < 0: return
    var piece = game.position.board[square.y][square.x]
    if piece != null and piece.side == game.position.side:
        selected = square
        board_view.show_moves(selected,game.legal_moves())
        message = "Elige una casilla iluminada"
        changed.emit()
    elif selected.x >= 0 and game.is_legal(game.position,selected.x,selected.y,square.x,square.y):
        if game.position.board[selected.y][selected.x].type == "pawn" and square.y in [0,7]:
            pending = square
            promotion_requested.emit()
        else:
            execute_move(selected,square,"queen")
    else:
        message = "Ese movimiento no es legal"
        changed.emit()

func promote(kind):
    if pending.x < 0: return
    var destination = pending
    pending = Vector2i(-1,-1)
    execute_move(selected,destination,kind)

func execute_move(from, to, promotion = "queen"):
    if busy: return false
    var before = game.position.board.duplicate(true)
    if not game.play(from.x,from.y,to.x,to.y,promotion): return false
    busy = true
    selected = Vector2i(-1,-1)
    board_view.show_moves(selected,[])
    message = "Combate arcano" if before[to.y][to.x] != null else "Moviendo pieza"
    changed.emit()
    await board_view.animate_move({"fx":from.x,"fy":from.y,"tx":to.x,"ty":to.y},before,game.position.board,animation_seconds)
    busy = false
    message = "Selecciona una pieza"
    changed.emit()
    maybe_bot()
    return true

func maybe_bot():
    if not bot_enabled or busy or pending.x >= 0 or game.position.side != "black" or game.status().terminal:
        return
    busy = true
    message = "Obsidiana está pensando…"
    changed.emit()
    var ticket = generation
    await get_tree().create_timer(0.3).timeout
    if ticket != generation:
        return
    var moves = game.legal_moves()
    var best = {}
    var best_score = -INF
    var values = {"pawn":1.0,"knight":3.0,"bishop":3.1,"rook":5.0,"queen":9.0,"king":0.0}
    for move in moves:
        var next = game.apply_unchecked(game.position,move)
        var score = 0.0
        for y in range(8):
            for x in range(8):
                var piece = next.board[y][x]
                if piece == null: continue
                var value = values[piece.type] + (3.5-abs(x-3.5))*0.025
                score += value if piece.side == "black" else -value
        # A bounded one-ply opponent capture check keeps the entry-level bot responsive.
        var moving = next.board[move.ty][move.tx]
        if game.attacked(next.board,move.tx,move.ty,"white"):
            score -= values[moving.type]*0.8
        if game.in_check(next,"white"): score += 0.15
        score += randf()*0.04
        if score > best_score:
            best = move
            best_score = score
    busy = false
    if not best.is_empty():
        execute_move(Vector2i(best.fx,best.fy),Vector2i(best.tx,best.ty),best.promotion if best.promotion != "" else "queen")

func reset_game():
    if busy: return
    generation += 1
    game.reset()
    selected = Vector2i(-1,-1)
    pending = Vector2i(-1,-1)
    board_view.show_moves(selected,[])
    board_view.sync(game.position.board)
    message = "Partida nueva"
    changed.emit()

func undo_move():
    if busy or pending.x >= 0: return
    if game.undo():
        if bot_enabled and game.position.side == "black": game.undo()
        selected = Vector2i(-1,-1)
        board_view.show_moves(selected,[])
        board_view.sync(game.position.board)
        message = "Movimiento deshecho"
        changed.emit()

func toggle_bot(enabled):
    if busy: return
    bot_enabled = enabled
    changed.emit()
    maybe_bot()

func save_game():
    if busy or pending.x >= 0: return
    var first = game.history[0] if not game.history.is_empty() else game.position
    var data = {"version":1,"start":game.to_fen(first),"moves":game.notation,"claimed_draw":game.claimed_draw,"bot":bot_enabled}
    var file = FileAccess.open(save_path+".tmp",FileAccess.WRITE)
    if file == null:
        message = "No se pudo guardar la partida"
    else:
        file.store_string(JSON.stringify(data))
        file.close()
        var error = DirAccess.rename_absolute(save_path+".tmp",save_path)
        message = "Partida guardada" if error == OK else "No se pudo sustituir el guardado"
    changed.emit()

func load_game():
    if busy or pending.x >= 0: return
    var file = FileAccess.open(save_path,FileAccess.READ)
    if file == null or file.get_length() > 1000000:
        message = "No hay un guardado válido"
        changed.emit()
        return
    var data = JSON.parse_string(file.get_as_text())
    file.close()
    if not restore_data(data):
        message = "Guardado inválido; se conserva la partida actual"
    else:
        board_view.sync(game.position.board)
        board_view.show_moves(Vector2i(-1,-1),[])
        message = "Partida recuperada"
        maybe_bot()
    changed.emit()

func restore_data(data) -> bool:
    if not data is Dictionary or data.get("version") != 1 or not data.get("start") is String or not data.get("moves") is Array or data.moves.size() > 2000:
        return false
    var restored = Game.new()
    if not restored.load_fen(data.start): return false
    for move in data.moves:
        if not move is String or move.length() not in [4,5]: return false
        if move[0] not in "abcdefgh" or move[2] not in "abcdefgh" or move[1] not in "12345678" or move[3] not in "12345678": return false
        var promotion = "queen"
        if move.length() == 5:
            promotion = {"q":"queen","r":"rook","b":"bishop","n":"knight"}.get(move[4],"")
            if promotion == "": return false
        if not restored.play("abcdefgh".find(move[0]),int(move[1])-1,"abcdefgh".find(move[2]),int(move[3])-1,promotion): return false
    if data.get("claimed_draw",false) and not restored.claim_draw(): return false
    game = restored
    selected = Vector2i(-1,-1)
    pending = Vector2i(-1,-1)
    bot_enabled = bool(data.get("bot",true))
    return true
