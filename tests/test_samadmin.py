from igris_os.samadmin import (SamadminApprovalAuthority, SamadminClient,
                               SamadminServer, SamadminStore)


def test_samadmin_approves_and_consumes_exact_request_once(tmp_path):
    store = SamadminStore(tmp_path)
    approval = store.create("crea una app", "project.lead", "write")

    assert store.get(approval.request_id).status == "pending"
    assert store.decide(approval.request_id, approved=True, operator="Samadmin")
    assert store.consume(approval.request_id, "crea una app", "project.lead", "write")
    assert not store.consume(approval.request_id, "crea una app", "project.lead", "write")


def test_samadmin_rejects_wrong_binding_and_stage(tmp_path):
    store = SamadminStore(tmp_path)
    approval = store.create("crea una app", "project.lead", "write")
    store.decide(approval.request_id, approved=True, operator="Samadmin")

    assert not store.consume(approval.request_id, "otro", "project.lead", "write")
    assert not store.consume(approval.request_id, "crea una app", "project.lead", "deliver")


def test_samadmin_http_requires_admin_decision_and_consumes_once(tmp_path):
    server = SamadminServer(tmp_path, admin_token="test-token", port=0)
    server.start()
    try:
        client = SamadminClient(server.url)
        request = client.request("crea una app", "project.lead", "write")
        assert not client.consume(request["request_id"], "crea una app", "project.lead", "write")
        decision = client.decide(
            request["request_id"], approved=True, operator="Samadmin",
            admin_token="test-token")
        assert decision["status"] == "approved"
        assert client.consume(request["request_id"], "crea una app", "project.lead", "write")
        assert not client.consume(request["request_id"], "crea una app", "project.lead", "write")
    finally:
        server.close()


def test_samadmin_authority_maps_capability_to_stage(tmp_path):
    server = SamadminServer(tmp_path, admin_token="test-token", port=0)
    server.start()
    try:
        client = SamadminClient(server.url)
        authority = SamadminApprovalAuthority(client)
        token = authority.issue("planifica", "project.plan")
        pending = client.status(token)
        assert pending["stage"] == "plan"
        client.decide(token, approved=True, operator="Samadmin", admin_token="test-token")
        assert authority.verify(token, "planifica", "project.plan")
    finally:
        server.close()


def test_samadmin_client_lists_pending_requests(tmp_path):
    server = SamadminServer(tmp_path, admin_token="test-token", port=0)
    server.start()
    try:
        client = SamadminClient(server.url)
        created = client.request("crea una app", "project.lead", "write")
        assert [item["request_id"] for item in client.pending()] == [created["request_id"]]
    finally:
        server.close()