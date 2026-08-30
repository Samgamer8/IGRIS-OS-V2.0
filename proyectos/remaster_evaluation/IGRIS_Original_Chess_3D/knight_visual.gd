class_name KnightVisual extends RefCounted

func build(material: Material) -> Node3D:
    var root = MeshInstance3D.new()
    root.name = "Knight"

    var base_mesh = CylinderMesh.new()
    base_mesh.top_radius = 0.2
    base_mesh.bottom_radius = 0.2
    base_mesh.height = 0.5
    var base = MeshInstance3D.new()
    base.mesh = base_mesh
    base.material_override = material
    base.rotation = Vector3(0, 0, 0)
    root.add_child(base)

    var neck_mesh = CylinderMesh.new()
    neck_mesh.top_radius = 0.1
    neck_mesh.bottom_radius = 0.1
    neck_mesh.height = 0.2
    var neck = MeshInstance3D.new()
    neck.mesh = neck_mesh
    neck.material_override = material
    neck.rotation = Vector3(0, 0, 0)
    neck.position = Vector3(0, 0.5, 0)
    root.add_child(neck)

    var head_mesh = SphereMesh.new()
    head_mesh.radius = 0.3
    var head = MeshInstance3D.new()
    head.mesh = head_mesh
    head.material_override = material
    head.rotation = Vector3(0, 0, 0)
    head.position = Vector3(0, 0.7, 0)
    root.add_child(head)

    var ear1_mesh = CylinderMesh.new()
    ear1_mesh.top_radius = 0.1
    ear1_mesh.bottom_radius = 0.1
    ear1_mesh.height = 0.2
    var ear1 = MeshInstance3D.new()
    ear1.mesh = ear1_mesh
    ear1.material_override = material
    ear1.rotation = Vector3(0, 0, 0)
    ear1.position = Vector3(0.2, 0.8, 0.2)
    root.add_child(ear1)

    var ear2_mesh = CylinderMesh.new()
    ear2_mesh.top_radius = 0.1
    ear2_mesh.bottom_radius = 0.1
    ear2_mesh.height = 0.2
    var ear2 = MeshInstance3D.new()
    ear2.mesh = ear2_mesh
    ear2.material_override = material
    ear2.rotation = Vector3(0, 0, 0)
    ear2.position = Vector3(-0.2, 0.8, 0.2)
    root.add_child(ear2)

    return root