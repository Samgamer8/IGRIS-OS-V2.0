import zipfile

from tools.package_production_rc import DOCS, package


def test_production_package_contains_certified_binary_and_scope(tmp_path):
    bundle = tmp_path / "dist" / "IGRIS OS RC1"
    bundle.mkdir(parents=True)
    (bundle / "IGRIS OS RC1.exe").write_bytes(b"rc")
    (bundle / "SHA256SUMS.txt").write_text("hash  exe\n", encoding="ascii")
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
    assert "IGRIS OS RC1/IGRIS OS RC1.exe" in names
    assert "IGRIS OS RC1/docs/RC_CAPABILITY_SCOPE.md" in names
    assert "IGRIS OS RC1/MANIFEST.sha256" in names
