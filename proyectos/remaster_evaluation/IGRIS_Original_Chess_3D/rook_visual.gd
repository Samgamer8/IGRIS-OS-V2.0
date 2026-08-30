class_name RookVisual extends RefCounted

func build(material: Material) -> Node3D:
    var root = MeshInstance3D.new()
    var base_mesh = BoxMesh.new()
    var trunk_mesh = CylinderMesh.new()
    var crown_mesh = BoxMesh.new()
    var battlement_mesh = BoxMesh.new()

    var base = MeshInstance3D.new()
    var trunk = MeshInstance3D.new()
    var crown = MeshInstance3D.new()
    var battlement1 = MeshInstance3D.new()
    var battlement2 = MeshInstance3D.new()
    var battlement3 = MeshInstance3D.new()
    var battlement4 = MeshInstance3D.new()

    base.mesh = base_mesh
    trunk.mesh = trunk_mesh
    crown.mesh = crown_mesh
    battlement1.mesh = battlement_mesh
    battlement2.mesh = battlement_mesh
    battlement3.mesh = battlement_mesh
    battlement4.mesh = battlement_mesh

    base.scale = Vector3(2, 0.5, 2)
    trunk.scale = Vector3(1, 1, 1)
    crown.scale = Vector3(1, 0.5, 1)
    battlement1.scale = Vector3(0.5, 1, 0.5)
    battlement2.scale = Vector3(0.5, 1, 0.5)
    battlement3.scale = Vector3(0.5, 1, 0.5)
    battlement4.scale = Vector3(0.5, 1, 0.5)

    base.position = Vector3(0, -0.75, 0)
    trunk.position = Vector3(0, 0, 0)
    crown.position = Vector3(0, 1.25, 0)
    battlement1.position = Vector3(-1.5, 1.75, 0)
    battlement2.position = Vector3(1.5, 1.75, 0)
    battlement3.position = Vector3(0, 1.75, -1.5)
    battlement4.position = Vector3(0, 1.75, 1.5)

    base.material_override = material
    trunk.material_override = material
    crown.material_override = material
    battlement1.material_override = material
    battlement2.material_override = material
    battlement3.material_override = material
    battlement4.material_override = material

    root.add_child(base)
    root.add_child(trunk)
    root.add_child(crown)
    root.add_child(battlement1)
    root.add_child(battlement2)
    root.add_child(battlement3)
    root.add_child(battlement4)

    return root