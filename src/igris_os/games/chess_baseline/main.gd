extends Node3D
const Board = preload("res://board_view.gd")
const Camera = preload("res://camera_controller.gd")
const Controller = preload("res://game_controller.gd")
var board
var camera
var controller
var status_label: Label
var detail_label: Label
var moves_label: Label
var buttons: Array = []
var bot: CheckButton
var promotion_panel: PanelContainer
var draw_button: Button
var capture_path = ""
var frames = 0

func _ready():
    board = Board.new()
    add_child(board)
    camera = Camera.new()
    add_child(camera)
    controller = Controller.new()
    add_child(controller)
    build_world()
    build_ui()
    controller.changed.connect(refresh)
    controller.promotion_requested.connect(func(): promotion_panel.show())
    controller.connect_scene(board,camera)
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--igris-capture="):
            capture_path = arg.trim_prefix("--igris-capture=")
    print("IGRIS_CHESS_READY")

func build_world():
    var environment = WorldEnvironment.new()
    var env = Environment.new()
    env.background_mode = Environment.BG_COLOR
    env.background_color = Color("101821")
    env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
    env.ambient_light_color = Color("9aadc7")
    env.ambient_light_energy = 0.40
    env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
    environment.environment = env
    add_child(environment)
    var key = DirectionalLight3D.new()
    key.rotation_degrees = Vector3(-55,-25,0)
    key.light_color = Color("fff0d4")
    key.light_energy = 0.85
    key.shadow_enabled = true
    add_child(key)
    var f = board.factory
    var stone = f.material(Color("212630"),0.1)
    f.part(self,f.box(Vector3(36,0.15,36)),Vector3(0,-0.95,0),stone)
    for x in [-5.3,5.3]:
        for z in [-5.3,5.3]:
            f.part(self,f.cylinder(0.38,0.65,2.6),Vector3(x,0.35,z),stone)
            f.part(self,f.cylinder(0.64,0.42,0.25),Vector3(x,1.7,z),f.gold)
            f.part(self,f.sphere(0.18),Vector3(x,1.96,z),f.blue if z > 0 else f.red)
            var light = OmniLight3D.new()
            light.position = Vector3(x,2.1,z)
            light.light_color = Color("64cfff") if z > 0 else Color("ff9561")
            light.light_energy = 1.1
            light.omni_range = 8
            add_child(light)
    for x in range(-7,8,2):
        f.part(self,f.box(Vector3(1.1,2.3,0.7)),Vector3(x,0.05,-7.8),stone)
        f.part(self,f.box(Vector3(1.2,0.25,0.8)),Vector3(x,1.35,-7.8),f.gold)

func label(text, size, color = Color("e2e7ea")) -> Label:
    var item = Label.new()
    item.text = text
    item.add_theme_font_size_override("font_size",size)
    item.add_theme_color_override("font_color",color)
    return item

func style(color, border = Color("4e4b48")):
    var panel = StyleBoxFlat.new()
    panel.bg_color = color
    panel.border_color = border
    panel.set_border_width_all(1)
    panel.set_corner_radius_all(8)
    panel.content_margin_left = 16
    panel.content_margin_right = 16
    panel.content_margin_top = 12
    panel.content_margin_bottom = 12
    return panel

func button(text, callback, column):
    var b = Button.new()
    b.text = text
    b.custom_minimum_size.y = 38
    b.add_theme_stylebox_override("normal",style(Color("253540")))
    b.add_theme_stylebox_override("hover",style(Color("354b57"),Color("c4a36c")))
    b.pressed.connect(callback)
    column.add_child(b)
    buttons.append(b)
    return b

func build_ui():
    var layer = CanvasLayer.new()
    add_child(layer)
    var title = VBoxContainer.new()
    title.position = Vector2(28,22)
    title.mouse_filter = Control.MOUSE_FILTER_IGNORE
    layer.add_child(title)
    title.add_child(label("IGRIS CHEES",30,Color("e6cb93")))
    title.add_child(label("MARFIL  /  OBSIDIANA",13,Color("95b9ca")))
    var panel = PanelContainer.new()
    panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_RIGHT)
    panel.offset_left = -298
    panel.offset_right = -24
    panel.offset_top = 24
    panel.add_theme_stylebox_override("panel",style(Color(0.07,0.10,0.13,0.95)))
    layer.add_child(panel)
    var col = VBoxContainer.new()
    col.add_theme_constant_override("separation",10)
    panel.add_child(col)
    col.add_child(label("LA CÁMARA ARCANA",14,Color("d4b27c")))
    status_label = label("",23)
    col.add_child(status_label)
    detail_label = label("",14,Color("b1c2c9"))
    detail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    detail_label.custom_minimum_size = Vector2(235,56)
    col.add_child(detail_label)
    bot = CheckButton.new()
    bot.text = "Rival automático · básico"
    bot.button_pressed = true
    bot.toggled.connect(controller.toggle_bot)
    col.add_child(bot)
    button("Nueva partida",controller.reset_game,col)
    button("Deshacer",controller.undo_move,col)
    button("Guardar partida",controller.save_game,col)
    button("Cargar partida",controller.load_game,col)
    button("Restablecer cámara",camera.reset_view,col)
    draw_button = button("Reclamar tablas",func():
        controller.game.claim_draw()
        refresh(),col)
    moves_label = label("",14,Color("d1bea0"))
    moves_label.custom_minimum_size.y = 80
    col.add_child(moves_label)
    var help = label("Clic: pieza y destino\nBotón derecho: girar\nRueda: acercar / alejar",13,Color("92a7b4"))
    col.add_child(help)
    promotion_panel = PanelContainer.new()
    promotion_panel.position = Vector2(300,280)
    promotion_panel.add_theme_stylebox_override("panel",style(Color("1a2a36"),Color("d4b27c")))
    layer.add_child(promotion_panel)
    var options = VBoxContainer.new()
    promotion_panel.add_child(options)
    options.add_child(label("Elige tu promoción",23))
    for pair in [["Reina","queen"],["Torre","rook"],["Alfil","bishop"],["Caballo","knight"]]:
        var choice = Button.new()
        choice.text = pair[0]
        choice.custom_minimum_size = Vector2(200,42)
        choice.pressed.connect(func():
            promotion_panel.hide()
            controller.promote(pair[1]))
        options.add_child(choice)
    promotion_panel.hide()

func refresh():
    var info = controller.game.status()
    status_label.text = "Marfil" if controller.game.position.side == "white" else "Obsidiana"
    detail_label.text = info.label + "\n" + controller.message
    for item in buttons: item.disabled = controller.busy or controller.pending.x >= 0
    draw_button.disabled = controller.busy or not info.claimable
    bot.disabled = controller.busy or controller.pending.x >= 0
    bot.set_pressed_no_signal(controller.bot_enabled)
    var history = controller.game.notation
    var start = max(0,history.size()-6)
    var lines = "ÚLTIMOS MOVIMIENTOS\n"
    for index in range(start,history.size()):
        lines += "%s. %s  " % [int(index/2)+1,history[index]]
        if index % 2: lines += "\n"
    moves_label.text = lines

func _process(_delta):
    frames += 1
    if capture_path != "" and frames == 10:
        await RenderingServer.frame_post_draw
        var error = get_viewport().get_texture().get_image().save_png(capture_path)
        if error == OK: print("IGRIS_3D_CAPTURE_SAVED")
        else: push_error("No se pudo guardar la captura")
        get_tree().quit(0 if error == OK else 1)
