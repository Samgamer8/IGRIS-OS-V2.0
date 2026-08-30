class_name QueenVisual extends RefCounted

func build(material: Material) -> Node3D:
    var root = Node3D.new()

    # Base
    var base_mesh = CylinderMesh.new()
    base_mesh.top_radius = 0.5
    base_mesh.bottom_radius = 0.5
    base_mesh.height = 1.0
    var base = MeshInstance3D.new()
    base.mesh = base_mesh
    base.material_override = material
    root.add_child(base)

    # Torso
    var torso_mesh = CylinderMesh.new()
    torso_mesh.top_radius = 0.5
    torso_mesh.bottom_radius = 0.5
    torso_mesh.height = 2.0
    var torso = MeshInstance3D.new()
    torso.mesh = torso_mesh
    torso.material_override = material
    torso.position = Vector3(0, 1.5, 0)
    root.add_child(torso)

    # Shoulders
    var shoulder_mesh = CylinderMesh.new()
    shoulder_mesh.top_radius = 0.3
    shoulder_mesh.bottom_radius = 0.3
    shoulder_mesh.height = 0.5
    var shoulder1 = MeshInstance3D.new()
    shoulder1.mesh = shoulder_mesh
    shoulder1.material_override = material
    shoulder1.position = Vector3(0.5, 2.5, 0)
    root.add_child(shoulder1)

    var shoulder2 = MeshInstance3D.new()
    shoulder2.mesh = shoulder_mesh
    shoulder2.material_override = material
    shoulder2.position = Vector3(-0.5, 2.5, 0)
    root.add_child(shoulder2)

    # Head
    var head_mesh = SphereMesh.new()
    head_mesh.radius = 0.5
    var head = MeshInstance3D.new()
    head.mesh = head_mesh
    head.material_override = material
    head.position = Vector3(0, 3.5, 0)
    root.add_child(head)

    # Crown Ring
    var crown_mesh = TorusMesh.new()
    crown_mesh.outer_radius = 0.5
    crown_mesh.inner_radius = 0.1
    var crown = MeshInstance3D.new()
    crown.mesh = crown_mesh
    crown.material_override = material
    crown.position = Vector3(0, 4.5, 0)
    root.add_child(crown)

    # Crown Points
    var crown_point1_mesh = CylinderMesh.new()
    crown_point1_mesh.top_radius = 0.1
    crown_point1_mesh.bottom_radius = 0.1
    crown_point1_mesh.height = 0.5
    var crown_point1 = MeshInstance3D.new()
    crown_point1.mesh = crown_point1_mesh
    crown_point1.material_override = material
    crown_point1.position = Vector3(0.3, 4.8, 0)
    root.add_child(crown_point1)

    var crown_point2_mesh = CylinderMesh.new()
    crown_point2_mesh.top_radius = 0.1
    crown_point2_mesh.bottom_radius = 0.1
    crown_point2_mesh.height = 0.5
    var crown_point2 = MeshInstance3D.new()
    crown_point2.mesh = crown_point2_mesh
    crown_point2.material_override = material
    crown_point2.position = Vector3(-0.3, 4.8, 0)
    root.add_child(crown_point2)

    return root