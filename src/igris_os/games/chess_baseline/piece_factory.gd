extends RefCounted
# Procedural low-poly fantasy pieces. Shared materials, independent articulated nodes.
var light = material(Color("dbe8eb"), 0.6)
var dark = material(Color("30314a"), 0.7)
var gold = material(Color("bd9351"), 0.8)
var blue = material(Color("45d4ff"), 0.3, true)
var red = material(Color("f47779"), 0.3, true)

func material(color: Color, metallic = 0.0, glowing = false):
    var m = StandardMaterial3D.new()
    m.albedo_color = color
    m.metallic = metallic
    m.roughness = 0.35
    if glowing:
        m.emission_enabled = true
        m.emission = color
        m.emission_energy_multiplier = 1.8
    return m

func part(root, mesh, pos, mat, rotation = Vector3.ZERO):
    var node = MeshInstance3D.new()
    node.mesh = mesh
    node.position = pos
    node.rotation_degrees = rotation
    node.material_override = mat
    root.add_child(node)
    return node

func cylinder(top, bottom, height):
    var m = CylinderMesh.new()
    m.top_radius = top
    m.bottom_radius = bottom
    m.height = height
    m.radial_segments = 12
    return m

func box(size):
    var m = BoxMesh.new()
    m.size = size
    return m

func sphere(radius):
    var m = SphereMesh.new()
    m.radius = radius
    m.height = radius * 2
    m.radial_segments = 12
    m.rings = 6
    return m

func create_piece(piece_type, side):
    var root = Node3D.new()
    var mat = light if side == "white" else dark
    var magic = blue if side == "white" else red
    part(root, cylinder(0.35,0.39,0.12), Vector3(0,0.06,0), gold)
    part(root, cylinder(0.30,0.34,0.08), Vector3(0,0.16,0), mat)
    var figure = Node3D.new()
    figure.name = "Figure"
    root.add_child(figure)
    var height = {"pawn":0.66,"rook":0.74,"knight":0.9,"bishop":1.04,"queen":1.11,"king":1.2}.get(piece_type,0.7)
    part(figure, cylinder(0.12,0.26,height * 0.55), Vector3(0,0.25+height * 0.24,0), mat)
    if piece_type == "rook":
        part(figure, cylinder(0.31,0.27,0.14), Vector3(0,0.86,0), gold)
        for x in [-1,1]:
            for z in [-1,1]:
                part(figure, box(Vector3(0.15,0.22,0.15)),Vector3(x*0.2,0.99,z*0.2),mat)
        part(figure, sphere(0.11),Vector3(0,0.92,0),magic)
    elif piece_type == "knight":
        part(figure, box(Vector3(0.21,0.48,0.24)),Vector3(0,0.7,0),mat,Vector3(-22,0,0))
        part(figure, box(Vector3(0.23,0.22,0.4)),Vector3(0,0.96,-0.13),mat,Vector3(-12,0,0))
        for x in [-1,1]:
            part(figure,cylinder(0.0,0.07,0.25),Vector3(x*0.10,1.14,-0.03),gold)
            part(figure,sphere(0.035),Vector3(x*0.12,1.0,-0.22),magic)
    else:
        part(figure,sphere(0.14),Vector3(0,height+0.02,0),mat)
        part(figure,box(Vector3(0.45,0.13,0.21)),Vector3(0,height-0.15,0),gold)
        if piece_type == "pawn":
            for x in [-1,1]:
                part(figure,box(Vector3(0.12,0.3,0.09)),Vector3(x*0.25,0.65,0.04),mat,Vector3(0,0,x*33))
        if piece_type == "bishop":
            part(figure,cylinder(0.0,0.17,0.35),Vector3(0,1.28,0),gold)
            part(figure,cylinder(0.025,0.025,0.85),Vector3(0.27,0.75,-0.04),gold,Vector3(0,0,-8))
            part(figure,sphere(0.07),Vector3(0.32,1.18,-0.04),magic)
        if piece_type in ["queen","king"]:
            part(figure,cylinder(0.19,0.15,0.09),Vector3(0,height+0.15,0),gold)
            for angle in range(0,360,60):
                var a = deg_to_rad(angle)
                part(figure,cylinder(0.0,0.045,0.19),Vector3(cos(a)*0.15,height+0.24,sin(a)*0.15),gold)
        if piece_type == "king":
            part(figure,box(Vector3(0.055,0.32,0.055)),Vector3(0,1.59,0),gold)
            part(figure,box(Vector3(0.22,0.05,0.055)),Vector3(0,1.62,0),gold)
        # Sword and shield on the articulated figure.
        part(figure,box(Vector3(0.045,0.42,0.05)),Vector3(-0.26,height-0.04,-0.12),gold,Vector3(0,0,-20))
        part(figure,box(Vector3(0.18,0.045,0.07)),Vector3(-0.22,height-0.19,-0.12),gold)
        part(figure,box(Vector3(0.20,0.30,0.065)),Vector3(0.25,height-0.22,-0.12),mat,Vector3(0,0,12))
        part(figure,sphere(0.052),Vector3(0,height-0.23,-0.15),magic)
    if side == "black": figure.rotation.y = PI
    return root
