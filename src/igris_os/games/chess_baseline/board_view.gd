extends Node3D
const Factory = preload("res://piece_factory.gd")
var factory = Factory.new()
var pieces: Dictionary = {}
var highlights: Node3D
var board_size = 8

func _ready():
    var pale = factory.material(Color("989e9b"),0.25)
    var charcoal = factory.material(Color("242d37"),0.35)
    factory.part(self,factory.box(Vector3(8.7,0.5,8.7)),Vector3(0,-0.30,0),factory.gold)
    factory.part(self,factory.box(Vector3(8.9,0.14,8.9)),Vector3(0,-0.59,0),charcoal)
    for y in range(8):
        for x in range(8):
            factory.part(self,factory.box(Vector3(0.985,0.12,0.985)),Vector3(x-3.5,-0.07,3.5-y),pale if (x+y)%2 else charcoal)
    for index in range(8):
        var file_label = Label3D.new()
        file_label.text = "ABCDEFGH"[index]
        file_label.position = Vector3(index-3.5,0.01,4.18)
        file_label.rotation_degrees.x = -90
        file_label.font_size = 38
        file_label.pixel_size = 0.006
        file_label.modulate = Color("dcc998")
        add_child(file_label)
    highlights = Node3D.new()
    add_child(highlights)

func square_position(x, y):
    return Vector3(x-3.5,0,3.5-y)

func sync(board):
    for node in pieces.values():
        node.free()
    pieces.clear()
    for y in range(8):
        for x in range(8):
            var piece = board[y][x]
            if piece != null:
                var node = factory.create_piece(piece.type,piece.side)
                node.position = square_position(x,y)
                add_child(node)
                pieces[Vector2i(x,y)] = node

func show_moves(selected, moves):
    for child in highlights.get_children(): child.free()
    if selected.x < 0: return
    var gold = factory.material(Color("e6ba65"),0.2,true)
    var cyan = factory.material(Color("48c5c0"),0.2,true)
    var ring = TorusMesh.new()
    ring.inner_radius = 0.36
    ring.outer_radius = 0.42
    factory.part(highlights,ring,square_position(selected.x,selected.y)+Vector3(0,0.07,0),gold)
    for move in moves:
        if move.fx == selected.x and move.fy == selected.y:
            factory.part(highlights,factory.cylinder(0.10,0.10,0.02),square_position(move.tx,move.ty)+Vector3(0,0.08,0),cyan)

func pick(camera: Camera3D, mouse: Vector2) -> Vector2i:
    var ray_origin = camera.project_ray_origin(mouse)
    var ray_direction = camera.project_ray_normal(mouse)
    var point = Plane(Vector3.UP,0.0).intersects_ray(ray_origin,ray_direction)
    if point == null: return Vector2i(-1,-1)
    var x = int(floor(point.x+4.0))
    var y = int(floor(4.0-point.z))
    return Vector2i(x,y) if x >= 0 and x < 8 and y >= 0 and y < 8 else Vector2i(-1,-1)

func animate_move(move, before, after, duration):
    var from = Vector2i(move.fx,move.fy)
    var to = Vector2i(move.tx,move.ty)
    var actor = pieces.get(from)
    if actor == null:
        sync(after)
        return
    var victim_key = to
    if before[from.y][from.x].type == "pawn" and from.x != to.x and before[to.y][to.x] == null:
        victim_key = Vector2i(to.x,from.y)
    var victim = pieces.get(victim_key)
    var origin = actor.position
    var destination = square_position(to.x,to.y)
    var figure = actor.get_node("Figure")
    var initial_rotation = figure.rotation
    if victim != null:
        var approach = destination + (origin-destination).normalized()*0.7
        var tween = create_tween()
        tween.tween_property(actor,"position",approach,duration*0.4).set_trans(Tween.TRANS_SINE)
        tween.tween_property(figure,"rotation:z",-0.4,duration*0.12)
        tween.tween_property(figure,"rotation:z",0.5,duration*0.12)
        tween.tween_callback(magic_burst.bind(destination+Vector3(0,0.6,0)))
        tween.tween_property(victim,"rotation:x",PI/2,duration*0.2)
        tween.parallel().tween_property(victim,"scale",Vector3.ONE*0.01,duration*0.25)
        tween.tween_property(figure,"rotation",initial_rotation,duration*0.15)
        tween.tween_property(actor,"position",destination,duration*0.25)
        await tween.finished
    else:
        var tween = create_tween()
        tween.tween_property(actor,"position",(origin+destination)*0.5+Vector3(0,0.3,0),duration*0.5).set_trans(Tween.TRANS_SINE)
        tween.parallel().tween_property(figure,"rotation:z",0.10,duration*0.5)
        if before[from.y][from.x].type == "king" and abs(to.x-from.x) == 2:
            var rook_x = 7 if to.x > from.x else 0
            var rook_to = 5 if to.x > from.x else 3
            var rook = pieces.get(Vector2i(rook_x,from.y))
            if rook != null:
                tween.parallel().tween_property(rook,"position",square_position(rook_to,from.y),duration*0.5)
        tween.tween_property(actor,"position",destination,duration*0.5).set_trans(Tween.TRANS_SINE)
        tween.parallel().tween_property(figure,"rotation",initial_rotation,duration*0.5)
        await tween.finished
    sync(after)

func magic_burst(pos):
    var burst = Node3D.new()
    add_child(burst)
    burst.position = pos
    var ring = TorusMesh.new()
    ring.inner_radius = 0.15
    ring.outer_radius = 0.22
    factory.part(burst,ring,Vector3.ZERO,factory.blue)
    var tween = create_tween().set_parallel(true)
    tween.tween_property(burst,"scale",Vector3.ONE*5,0.45)
    tween.tween_property(burst,"position:y",pos.y+0.8,0.45)
    tween.chain().tween_callback(burst.queue_free)
