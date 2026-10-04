extends Camera3D
var yaw = 0.35
var pitch = 0.85
var distance = 13.6

func _ready():
    current = true
    fov = 48
    h_offset = 1.2
    update_camera()

func reset_view():
    yaw = 0.35
    pitch = 0.85
    distance = 13.6
    update_camera()

func update_camera():
    position = Vector3(sin(yaw)*cos(pitch),sin(pitch),cos(yaw)*cos(pitch))*distance
    look_at(Vector3.ZERO,Vector3.UP)

func _unhandled_input(event):
    if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
        yaw -= event.relative.x*0.006
        pitch = clamp(pitch+event.relative.y*0.006,0.4,1.35)
        update_camera()
    if event is InputEventMouseButton and event.pressed:
        if event.button_index == MOUSE_BUTTON_WHEEL_UP: distance = max(9.0,distance-0.7)
        if event.button_index == MOUSE_BUTTON_WHEEL_DOWN: distance = min(23.0,distance+0.7)
        update_camera()
