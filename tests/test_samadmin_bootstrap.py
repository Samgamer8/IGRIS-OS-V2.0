from igris_os.bootstrap import build_igris
from igris_os.samadmin import SamadminApprovalAuthority, SamadminServer


def test_bootstrap_uses_samadmin_when_endpoint_is_configured(tmp_path, monkeypatch):
    server = SamadminServer(tmp_path / "samadmin", admin_token="test", port=0)
    server.start()
    try:
        monkeypatch.setenv("IGRIS_SAMADMIN_URL", server.url)
        kernel = build_igris(tmp_path / "runtime")
        assert isinstance(kernel.approval, SamadminApprovalAuthority)
    finally:
        server.close()