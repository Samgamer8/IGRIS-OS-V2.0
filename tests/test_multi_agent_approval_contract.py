from igris_os.multi_agent.coordinator import MultiAgentCoordinator


def test_review_approval_is_explicit_and_fail_closed():
    assert MultiAgentCoordinator._review_approved("APPROVED")
    assert MultiAgentCoordinator._review_approved("Review complete\nAPPROVED.")
    assert not MultiAgentCoordinator._review_approved("NOT APPROVED")
    assert not MultiAgentCoordinator._review_approved(
        "The implementation is not approved due to failed tests.")
    assert not MultiAgentCoordinator._review_approved("no issues mentioned")
