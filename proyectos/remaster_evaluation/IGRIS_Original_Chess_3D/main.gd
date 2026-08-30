extends Node3D

@export var capture_path = ""

var game_controller: GameController
var camera_controller: CameraController
var hud: CanvasLayer
var label: Label

func _ready():
	# Parse command line arguments
	var args = get_script_arguments()
	for arg in args:
		if arg.startswith("--igris-capture="):
			capture_path = arg.split("=")[1]
			break
			
	# Initialize game components
	game_controller = GameController.new()
	camera_controller = CameraController.new()
	add_child(game_controller)
	add_child(camera_controller)
	
	# Setup HUD
	hud = CanvasLayer.new()
	add_child(hud)
	
	label = Label.new()
	label.text = "Turn: White\nInstructions: Click to select and move pieces"
	label.rect_min_size = Vector2(200, 100)
	label.rect_position = Vector2(10, 10)
	hud.add_child(label)
	
	# Setup PBR lighting
	var ambient_light = AmbientLight.new()
	ambient_light.energy = 0.5
	add_child(ambient_light)
	
	var directional_light = DirectionalLight.new()
	directional_light.direction = Vector3(-1, -1, -1).normalized()
	directional_light.energy = 1.0
	add_child(directional_light)
	
	# Setup camera
	var camera = Camera3D.new()
	camera.transform.origin = Vector3(0, 10, 20)
	camera.transform.basis = Basis(Vector3(0, 1, 0), deg2rad(45))
	add_child(camera)
	
	camera_controller.camera = camera
	camera_controller.target = game_controller
	
	# Initialize game
	game_controller.initialize_board()
	
func _process(delta):
	# Update HUD
	label.text = "Turn: " + game_controller.chess_rules.current_turn + "\nInstructions: Click to select and move pieces"
	
	# Capture screenshot if path is set
	if capture_path != "" and Input.is_action_just_pressed("ui_accept"):
		var viewport = get_viewport()
		viewport.get_texture().get_data().save_png(capture_path)
		capture_path = ""  # Reset path to prevent multiple saves
