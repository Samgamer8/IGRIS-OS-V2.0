extends SceneTree
var failures: Array = []

func require(value, name):
    if not value:
        failures.append(name)
        push_error("IGRIS_CHESS_FAILED:" + name)
    return value

func _initialize():
    call_deferred("run_checks")

func run_checks():
    var game = load("res://chess_game.gd").new()
    require(game.legal_moves().size() == 20,"initial_20_legal_moves")
    require(game.is_legal(game.position,4,1,4,3),"white_pawn_double")
    require(not game.is_legal(game.position,4,1,4,4),"pawn_too_far")
    game.position.board[2][4] = {"type":"knight","side":"black"}
    require(not game.is_legal(game.position,4,1,4,3),"pawn_blocked")
    game.reset()
    require(game.play(4,1,4,3),"play_e2e4")
    require(game.is_legal(game.position,4,6,4,4),"black_pawn_double")
    game.reset()
    require(game.play(5,1,5,2) and game.play(4,6,4,4) and game.play(6,1,6,3) and game.play(3,7,7,3),"fools_mate_moves")
    require(game.status().terminal and game.status().check,"checkmate")
    require(game.load_fen("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"),"castle_fen")
    require(game.play(4,0,6,0),"castle_kingside")
    require(game.position.board[0][5].type == "rook" and game.position.board[0][7] == null,"castle_rook_moves")
    require(game.load_fen("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1"),"ep_fen")
    require(game.play(4,4,3,5),"en_passant")
    require(game.position.board[4][3] == null,"ep_removes_victim")
    require(game.load_fen("4k3/P7/8/8/8/8/8/4K3 w - - 0 1"),"promotion_fen")
    require(game.play(0,6,0,7,"knight") and game.position.board[7][0].type == "knight","underpromotion")
    require(game.load_fen("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"),"stalemate_fen")
    require(game.status().terminal and not game.status().check,"stalemate")
    var scene = load("res://main.tscn").instantiate()
    root.add_child(scene)
    await process_frame
    var control = scene.controller
    control.bot_enabled = false
    control.animation_seconds = 0.01
    require(scene.board.pieces.size() == 32,"32_piece_nodes")
    control.choose(Vector2i(4,1))
    control.choose(Vector2i(4,3))
    for wait_frame in range(240):
        if not control.busy: break
        await process_frame
    if not require(not control.busy and control.game.position.board[3][4] != null,"selection_to_animated_move"):
        scene.free()
        quit(1)
        return
    await control.execute_move(Vector2i(3,6),Vector2i(3,4))
    await control.execute_move(Vector2i(4,3),Vector2i(3,4))
    require(scene.board.pieces.size() == 31,"animated_capture_removes_visual")
    require(control.game.position.board[4][3].side == "white","capture_state")
    control.undo_move()
    require(scene.board.pieces.size() == 32,"undo_restores_capture")
    var current = control.game.to_fen()
    require(not control.restore_data({"version":1,"start":"invalid","moves":[]}),"reject_bad_save")
    require(control.game.to_fen() == current,"bad_save_preserves_game")
    require(control.restore_data({"version":1,"start":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1","moves":["e2e4","e7e5"],"bot":false}),"replay_saved_game")
    require(control.game.position.board[3][4] != null and control.game.position.board[4][4] != null,"saved_position")
    control.save_path = "user://igris-verification-"+str(Time.get_ticks_usec())+".json"
    var saved_fen = control.game.to_fen()
    control.save_game()
    require(FileAccess.file_exists(control.save_path),"write_actual_save")
    control.reset_game()
    control.load_game()
    require(control.game.to_fen() == saved_fen,"load_actual_save")
    DirAccess.remove_absolute(control.save_path)
    DirAccess.remove_absolute(control.save_path+".tmp")
    scene.free()
    await create_timer(0.05).timeout
    if failures.is_empty():
        print("IGRIS_CHESS_ACCEPTANCE_OK")
    quit(0 if failures.is_empty() else 1)
