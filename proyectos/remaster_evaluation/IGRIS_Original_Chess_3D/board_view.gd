extends Node3D

var board_size = 8
var pieces = []
var current_turn = "white"
var camera
var board_mesh
var board_material
var highlight_material
var highlight_mesh
var highlight_mesh_instance

func _ready():
    initialize_board()
    setup_camera()
    setup_lighting()
    setup_highlight()

func initialize_board():
    for i in range(board_size):
        for j in range(board_size):
            var piece_type = get_piece_type(i, j)
            if piece_type != "none":
                var piece = piece_factory.create_piece(piece_type, Vector3(i, board_size - j - 1, 0))
                add_child(piece)
                pieces.append([Vector2(i, j), piece])

func setup_camera():
    camera = Camera3D.new()
    add_child(camera)
    camera.rotation = Vector3(0, -PI / 4, 0)
    camera.position = Vector3(0, 10, 10)

func setup_lighting():
    var ambient_light = AmbientLight.new()
    add_child(ambient_light)
    ambient_light.color = Color(0.2, 0.2, 0.2)

    var directional_light = DirectionalLight.new()
    add_child(directional_light)
    directional_light.direction = Vector3(-1, -1, -1)
    directional_light.color = Color(0.8, 0.8, 0.8)

func setup_highlight():
    highlight_mesh = PlaneMesh.new()
    highlight_mesh.size = Vector2(1, 1)
    highlight_material = StandardMaterial3D.new()
    highlight_material.albedo_color = Color(1, 1, 1, 0.5)
    highlight_mesh_instance = MeshInstance3D.new()
    highlight_mesh_instance.mesh = highlight_mesh
    highlight_mesh_instance.material_override = highlight_material
    highlight_mesh_instance.visible = false
    add_child(highlight_mesh_instance)

func get_piece_type(i, j):
    if (i + j) % 2 == 0:
        if i < 2:
            return "black"
        elif i > 5:
            return "white"
        else:
            return "none"
    else:
        return "none"

func pick_piece(mouse_pos):
    var ray_origin = camera.project_ray_origin(mouse_pos)
    var ray_direction = camera.project_ray_normal(mouse_pos)
    var hit = get_tree().intersect_ray(ray_origin, ray_direction)
    if hit:
        var piece = hit.collider
        if piece is MeshInstance3D and piece.name.startswith("Piece_"):
            return piece
    return null

func highlight_piece(pos):
    highlight_mesh_instance.position = Vector3(pos[0], board_size - pos[1] - 1, 0)
    highlight_mesh_instance.scale = Vector3(1, 1, 1)
    highlight_mesh_instance.visible = true

func unhighlight_piece():
    highlight_mesh_instance.visible = false

func _input(event):
    if event is InputEventMouseButton and event.button_index == BUTTON_LEFT and event.pressed:
        var picked_piece = pick_piece(get_global_mouse_position())
        if picked_piece:
            var pos = get_piece_position(picked_piece)
            if is_valid_move(pos, Vector2(event.position.x, event.position.y)):
                make_move(pos, Vector2(event.position.x, event.position.y))
                unhighlight_piece()

func get_piece_position(piece):
    for p in pieces:
        if p[1] == piece:
            return p[0]
    return null

func is_valid_move(from_pos, to_pos):
    return chess_rules.is_valid_move(from_pos, to_pos)

func make_move(from_pos, to_pos):
    chess_rules.make_move(from_pos, to_pos)
    var from_index = from_pos[0] * board_size + from_pos[1]
    var to_index = to_pos[0] * board_size + to_pos[1]
    var from_piece = pieces[from_index][1]
    var to_piece = pieces[to_index][1]
    to_piece.position = Vector3(to_pos[0], board_size - to_pos[1] - 1, 0)
    pieces[to_index] = [to_pos, to_piece]
    pieces[from_index] = [from_pos, null]
    unhighlight_piece()
    current_turn = if current_turn == "white" then "black" else "white"

func _process(delta):
    pass
