import zipfile

from tools.package_final_rc import DOCS, package


def test_final_package_contains_binary_scope_and_manifest(tmp_path):
    bundle = tmp_path / "dist" / "IGRIS OS FINAL RC"
    bundle.mkdir(parents=True)
    (bundle / "IGRIS OS FINAL RC.exe").write_bytes(b"final")
    for name in DOCS:
        source = tmp_path / "docs" / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(name, encoding="utf-8")
    seller = tmp_path / "release" / "SELLER.example.json"
    seller.parent.mkdir()
    seller.write_text("{}\n", encoding="utf-8")

    archive = package(tmp_path)

    with zipfile.ZipFile(archive) as output:
        names = set(output.namelist())
    assert "IGRIS OS FINAL RC/IGRIS OS FINAL RC.exe" in names
    assert "IGRIS OS FINAL RC/docs/RC_CAPABILITY_SCOPE_FINAL.md" in names
    assert "IGRIS OS FINAL RC/MANIFEST.sha256" in names
