# -*- coding: utf-8 -*-
"""El token de aprobacion: vinculado, caduco y a prueba de manipulacion."""
from igris_os.application import ApprovalAuthority


def test_valid_token_verifies():
    authority = ApprovalAuthority()
    token = authority.issue("objetivo", "cap")
    assert authority.verify(token, "objetivo", "cap")


def test_tampered_token_rejected():
    authority = ApprovalAuthority()
    token = authority.issue("objetivo", "cap")
    prefix, signature = token.split(".", 1)
    forged = prefix + "." + ("0" if signature[0] != "0" else "1") + signature[1:]
    assert not authority.verify(forged, "objetivo", "cap")


def test_wrong_binding_rejected():
    authority = ApprovalAuthority()
    token = authority.issue("objetivo", "cap")
    assert not authority.verify(token, "otro objetivo", "cap")


def test_wrong_capability_rejected():
    authority = ApprovalAuthority()
    token = authority.issue("objetivo", "cap")
    assert not authority.verify(token, "objetivo", "otra")


def test_expired_token_rejected():
    authority = ApprovalAuthority(ttl_seconds=0)
    token = authority.issue("objetivo", "cap")
    assert not authority.verify(token, "objetivo", "cap")


def test_none_or_malformed_rejected():
    authority = ApprovalAuthority()
    assert not authority.verify(None, "objetivo", "cap")
    assert not authority.verify("no-es-un-token", "objetivo", "cap")
