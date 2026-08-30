extends RefCounted

var light_material = StandardMaterial3D.new()
var dark_material = StandardMaterial3D.new()

var pawn_builder = preload('res://pawn_visual.gd').new()
var rook_builder = preload('res://rook_visual.gd').new()
var knight_builder = preload('res://knight_visual.gd').new()
var bishop_builder = preload('res://bishop_visual.gd').new()
var queen_builder = preload('res://queen_visual.gd').new()
var king_builder = preload('res://king_visual.gd').new()

func _init():
    light_material.albedo_color = Color(1, 1, 1)
    light_material.metallic = 0.2
    light_material.roughness = 0.8
    dark_material.albedo_color = Color(0.8, 0.6, 0.4)
    dark_material.metallic = 0.1
    dark_material.roughness = 0.7

func create_piece(piece_type, side):
    var root = Node3D.new()
    var material = light_material if side == 'white' else dark_material
    match piece_type:
        'pawn':
            root.add_child(pawn_builder.build(material))
        'rook':
            root.add_child(rook_builder.build(material))
        'knight':
            root.add_child(knight_builder.build(material))
        'bishop':
            root.add_child(bishop_builder.build(material))
        'queen':
            root.add_child(queen_builder.build(material))
        'king':
            root.add_child(king_builder.build(material))
    return root