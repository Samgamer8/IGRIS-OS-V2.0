import hashlib
import json

from tools.release_candidate_check import REQUIRED_DOCS, inspect


def _technical_tree(tmp_path):
    for relative in REQUIRED_DOCS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("contenido\n", encoding="utf-8")
    bundle = tmp_path / "dist" / "IGRIS OS"
    bundle.mkdir(parents=True)
    executable = bundle / "IGRIS OS.exe"
    executable.write_bytes(b"binary")
    digest = hashlib.sha256(b"binary").hexdigest().upper()
    (bundle / "SHA256SUMS.txt").write_text(
        digest + "  IGRIS OS.exe\n", encoding="ascii")


def test_technical_release_can_pass_before_legal_configuration(tmp_path):
    _technical_tree(tmp_path)

    result = inspect(tmp_path)

    assert result.technical_ready
    assert not result.commercial_ready
    assert "Falta release/SELLER.json" in result.errors


def test_commercial_release_requires_complete_seller_identity(tmp_path):
    _technical_tree(tmp_path)
    seller = tmp_path / "release" / "SELLER.json"
    seller.parent.mkdir()
    seller.write_text(json.dumps({
        "legal_name": "IGRIS Example S.L.",
        "support_email": "support@example.com",
        "jurisdiction": "España",
    }), encoding="utf-8")

    result = inspect(tmp_path)

    assert result.technical_ready
    assert result.commercial_ready
    assert not result.errors


def test_release_rejects_tampered_executable(tmp_path):
    _technical_tree(tmp_path)
    executable = tmp_path / "dist" / "IGRIS OS" / "IGRIS OS.exe"
    executable.write_bytes(b"tampered")

    result = inspect(tmp_path)

    assert not result.technical_ready
    assert "SHA-256" in "; ".join(result.errors)
