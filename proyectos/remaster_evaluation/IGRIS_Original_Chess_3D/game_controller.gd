class_name GameController extends Node3D

var chess_rules: ChessRules
var board_view: BoardView
var camera_controller: CameraController
var selected_piece: MeshInstance3D
var selected_position: Vector2

func _ready():
	chess_rules = $ChessRules
	board_view = $BoardView
	camera_controller = $CameraController
	board_view.initialize_board()
	camera_controller.setup_camera()
	camera_controller.setup_lighting()
	camera_controller.setup_highlight()

func initialize_board():
	chess_rules.initialize_board()
	board_view.initialize_board()

func pick_piece(mouse_pos: Vector2):
	var picked_piece = board_view.pick_piece(mouse_pos)
	if picked_piece:
		selected_piece = picked_piece
		selected_position = board_view.get_piece_position(picked_piece)
		highlight_piece(selected_position)

func highlight_piece(pos: Vector2):
	board_view.highlight_piece(pos)

func unhighlight_piece():
	board_view.unhighlight_piece()

func _input(event):
	if event is InputEventMouseButton and event.button_index == BUTTON_LEFT and event.pressed:
		pick_piece(get_global_mouse_position())
		if selected_piece:
			var new_position = board_view.get_piece_position(selected_piece)
			if chess_rules.is_valid_move(selected_position, new_position):
				chess_rules.make_move(selected_position, new_position)
				board_view.update_board()
				unhighlight_piece()
				selected_piece = null
				selected_position = Vector2()
				camera_controller.reset_camera()
				yield(get_tree().create_tween(), "tween_completed")
				get_tree().create_tween().tween_property(selected_piece, "position", board_view.get_piece_position(chess_rules.get_piece(new_position)), 0.5, Tween.TRANS_LINEAR, Tween.EASE_IN_OUT)

func update_board():
	board_view.update_board()

func reset_game():
	chess_rules.initialize_board()
	board_view.initialize_board()
	unhighlight_piece()
	selected_piece = null
	selected_position = Vector2()
	camera_controller.reset_camera()
