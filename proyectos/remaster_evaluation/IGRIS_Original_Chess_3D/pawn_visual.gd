class_name PawnVisual extends RefCounted

func build(material: Material) -> Node3D:
    var root = MeshInstance3D.new()
    var disc_base = MeshInstance3D.new()
    var torso = MeshInstance3D.new()
    var head = MeshInstance3D.new()
    var wing1 = MeshInstance3D.new()
    var wing2 = MeshInstance3D.new()

    var disc_mesh = CylinderMesh.new()
    disc_mesh.top_radius = 0.1
    disc_mesh.bottom_radius = 0.1
    disc_mesh.height = 0.2
    disc_base.mesh = disc_mesh
    disc_base.scale = Vector3(1, 1, 1)
    disc_base.material_override = material
    root.add_child(disc_base)

    var torso_mesh = CylinderMesh.new()
    torso_mesh.top_radius = 0.15
    torso_mesh.bottom_radius = 0.15
    torso_mesh.height = 0.3
    torso.mesh = torso_mesh
    torso.scale = Vector3(1, 1, 1)
    torso.position = Vector3(0, 0.2, 0)
    torso.material_override = material
    root.add_child(torso)

    var head_mesh = SphereMesh.new()
    head_mesh.radius = 0.2
    head.mesh = head_mesh
    head.scale = Vector3(1, 1, 1)
    head.position = Vector3(0, 0.5, 0)
    head.material_override = material
    root.add_child(head)

    var wing_mesh = PlaneMesh.new()
    wing_mesh.size = Vector2(0.4, 0.1)
    wing1.mesh = wing_mesh
    wing1.scale = Vector3(1, 1, 1)
    wing1.position = Vector3(0.2, 0.6, 0.1)
    wing1.rotation = Vector3(0, 0, 0.785398)
    wing1.material_override = material
    root.add_child(wing1)

    wing2.mesh = wing_mesh
    wing2.scale = Vector3(1, 1, 1)
    wing2.position = Vector3(-0.2, 0.6, 0.1)
    wing2.rotation = Vector3(0, 0, -0.785398)
    wing2.material_override = material
    root.add_child(wing2)

    return root