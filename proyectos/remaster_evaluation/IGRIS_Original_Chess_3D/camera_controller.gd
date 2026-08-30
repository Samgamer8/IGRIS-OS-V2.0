extends Node3D

var camera: Camera3D
var target: Node3D
var distance = 10.0
var min_distance = 5.0
var max_distance = 20.0
var rotation_speed = 0.1
var orbit_speed = 0.1
var orbit_angle = 0.0
var target_angle = 0.0

func _ready():
	camera = $Camera
	target = $Target
	camera.position = target.position + Vector3(0, 0, distance)
	camera.look_at(target.position)

func _process(delta):
	var mouse_speed = Vector2(0, 0)
	if Input.is_action_pressed("ui_right"):
		mouse_speed.x += 1
	if Input.is_action_pressed("ui_left"):
		mouse_speed.x -= 1
	if Input.is_action_pressed("ui_down"):
		mouse_speed.y += 1
	if Input.is_action_pressed("ui_up"):
		mouse_speed.y -= 1
	
	orbit_angle += mouse_speed.x * orbit_speed * delta
	target_angle += mouse_speed.y * rotation_speed * delta
	
	var new_distance = distance - Input.mouse_wheel * 10 * delta
	new_distance = clamp(new_distance, min_distance, max_distance)
	
	camera.position = target.position + Vector3(
		new_distance * sin(orbit_angle) * cos(target_angle),
		new_distance * sin(target_angle),
		new_distance * cos(orbit_angle) * cos(target_angle)
	)
	camera.look_at(target.position)

func reset_camera():
	orbit_angle = 0.0
	target_angle = 0.0
	distance = 10.0
	camera.position = target.position + Vector3(0, 0, distance)
	camera.look_at(target.position)
