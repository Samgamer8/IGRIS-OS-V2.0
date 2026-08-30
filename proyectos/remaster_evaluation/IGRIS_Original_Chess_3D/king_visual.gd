class_name KingVisual extends RefCounted

func build(material: Material) -> Node3D:
    var root = Node3D.new()

    # Base
    var base_mesh = CylinderMesh.new()
    base_mesh.top_radius = 1.0
    base_mesh.bottom_radius = 1.0
    base_mesh.height = 0.5
    var base = MeshInstance3D.new()
    base.mesh = base_mesh
    base.material_override = material
    root.add_child(base)

    # Body
    var body_mesh = CylinderMesh.new()
    body_mesh.top_radius = 0.5
    body_mesh.bottom_radius = 0.5
    body_mesh.height = 2.0
    var body = MeshInstance3D.new()
    body.mesh = body_mesh
    body.position = Vector3(0, 1.25, 0)
    body.material_override = material
    root.add_child(body)

    # Shoulders
    var shoulder_mesh = CylinderMesh.new()
    shoulder_mesh.top_radius = 0.2
    shoulder_mesh.bottom_radius = 0.2
    shoulder_mesh.height = 0.5
    var shoulder1 = MeshInstance3D.new()
    shoulder1.mesh = shoulder_mesh
    shoulder1.position = Vector3(-0.5, 2.25, 0)
    shoulder1.material_override = material
    root.add_child(shoulder1)

    var shoulder2 = MeshInstance3D.new()
    shoulder2.mesh = shoulder_mesh
    shoulder2.position = Vector3(0.5, 2.25, 0)
    shoulder2.material_override = material
    root.add_child(shoulder2)

    # Cross
    var cross_base_mesh = BoxMesh.new()
    cross_base_mesh.size = Vector3(0.1, 0.1, 0.1)
    var cross_base1 = MeshInstance3D.new()
    cross_base1.mesh = cross_base_mesh
    cross_base1.position = Vector3(-0.5, 3.0, 0)
    cross_base1.material_override = material
    root.add_child(cross_base1)

    var cross_base2 = MeshInstance3D.new()
    cross_base2.mesh = cross_base_mesh
    cross_base2.position = Vector3(0.5, 3.0, 0)
    cross_base2.material_override = material
    root.add_child(cross_base2)

    var cross_cross_mesh = BoxMesh.new()
    cross_cross_mesh.size = Vector3(0.1, 0.1, 0.1)
    var cross_cross = MeshInstance3D.new()
    cross_cross.mesh = cross_cross_mesh
    cross_cross.position = Vector3(0, 3.5, 0)
    cross_cross.material_override = material
    root.add_child(cross_cross)

    return root