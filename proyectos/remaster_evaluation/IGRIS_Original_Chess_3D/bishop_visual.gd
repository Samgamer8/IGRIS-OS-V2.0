class_name BishopVisual extends RefCounted

func build(material: Material) -> Node3D:
    var root = MeshInstance3D.new()
    var base_mesh = CylinderMesh.new()
    var robe_mesh = CylinderMesh.new()
    var mitre_mesh = SphereMesh.new()
    var detail_mesh = PlaneMesh.new()

    var base = MeshInstance3D.new()
    var robe = MeshInstance3D.new()
    var mitre = MeshInstance3D.new()
    var detail = MeshInstance3D.new()

    base_mesh.top_radius = 0.1
    base_mesh.bottom_radius = 0.1
    base_mesh.height = 0.2

    robe_mesh.top_radius = 0.2
    robe_mesh.bottom_radius = 0.2
    robe_mesh.height = 0.5

    mitre_mesh.radius = 0.1
    mitre_mesh.height = 0.3

    detail_mesh.size = Vector2(0.1, 0.1)

    base.mesh = base_mesh
    robe.mesh = robe_mesh
    mitre.mesh = mitre_mesh
    detail.mesh = detail_mesh

    base.material_override = material
    robe.material_override = material
    mitre.material_override = material
    detail.material_override = material

    base.rotation = Vector3(0, 0, 0)
    robe.rotation = Vector3(0, 0, 0)
    mitre.rotation = Vector3(0, 0, 0)
    detail.rotation = Vector3(0, 0, 0)

    base.position = Vector3(0, 0, 0)
    robe.position = Vector3(0, 0.3, 0)
    mitre.position = Vector3(0, 0.8, 0)
    detail.position = Vector3(0.1, 0.8, 0.1)

    root.add_child(base)
    root.add_child(robe)
    root.add_child(mitre)
    root.add_child(detail)

    return root