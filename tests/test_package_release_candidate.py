import zipfile

from tools.package_release_candidate import DOCS, package


def test_package_contains_binary_docs_seller_example_and_manifest(tmp_path):
    bundle = tmp_path / "dist" / "IGRIS OS"
    bundle.mkdir(parents=True)
    (bundle / "IGRIS OS.exe").write_bytes(b"exe")
    for name in DOCS:
        path = tmp_path / "docs" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    seller = tmp_path / "release" / "SELLER.example.json"
    seller.parent.mkdir()
    seller.write_text("{}\n", encoding="utf-8")

    archive = package(tmp_path)

    assert archive.is_file()
    manifest = (bundle / "MANIFEST.sha256").read_text(encoding="ascii")
    assert "IGRIS OS.exe" in manifest
    assert "docs/USER_GUIDE.md" in manifest
    with zipfile.ZipFile(archive) as packaged:
        names = set(packaged.namelist())
    assert "IGRIS OS/IGRIS OS.exe" in names
    assert "IGRIS OS/SELLER.example.json" in names
    assert "IGRIS OS/MANIFEST.sha256" in names
