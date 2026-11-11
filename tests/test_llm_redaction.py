from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from llm.config import LLMSettings
from llm.payload import MessageInput, build_provider_payload
from llm.redact import OAuthTokenDetected, redact_sensitive


def fake_corpus() -> dict[str, str]:
    pan = "ABCDE" + "1234" + "F"
    aadhaar = "1234" + " 5678 9012"
    phone = "98765" + "43210"
    account = "654321" + "098765"
    card = "4111" + (" 1111" * 3)
    email = "person" + "@" + "example.invalid"
    upi_id = "person" + "@okaxis"
    reference = "123456" + "789012"
    amount = "123456" + "7890"
    return {
        "pan": pan,
        "aadhaar": aadhaar,
        "phone": phone,
        "account": account,
        "card": card,
        "email": email,
        "upi_id": upi_id,
        "reference": reference,
        "amount": amount,
    }


def test_redaction_masks_identifiers_but_preserves_amounts_and_references() -> None:
    values = fake_corpus()
    text = (
        f"PAN {values['pan']}; Aadhaar {values['aadhaar']}; phone {values['phone']}; "
        f"account {values['account']}; card {values['card']}; email {values['email']}; "
        f"UPI {values['upi_id']}; amount Rs {values['amount']}; "
        f"reference {values['reference']}; slash /{values['reference']}/; date 2026-01-02."
    )
    result = redact_sensitive(text)

    for sensitive in values.values():
        if sensitive in {values["amount"], values["reference"]}:
            continue
        assert sensitive not in result.redacted_text
    assert f"Rs {values['amount']}" in result.redacted_text
    assert values["reference"] in result.redacted_text
    assert "UPI" in result.redacted_text
    assert result.restore("<PAN_1>") == values["pan"]
    assert result.token_map


def test_reference_context_wins_before_aadhaar_shaped_masking() -> None:
    reference = "123456" + "789012"
    result = redact_sensitive(f"UPI Ref: {reference}; slash /{reference}/")
    assert reference in result.redacted_text
    assert result.token_map == {}


def test_generic_upi_handle_is_redacted_without_known_psp_suffix() -> None:
    handle = "payer" + "@bankhandle"
    result = redact_sensitive(handle)
    assert handle not in result.redacted_text


def test_redaction_result_keeps_token_map_in_memory_only() -> None:
    result = redact_sensitive("Contact person" + "@" + "example.invalid")
    assert "token_map" not in result.redacted_text
    assert "token_map" not in json.dumps({"redacted_text": result.redacted_text})
    assert result.token_map


def test_payload_contains_only_redacted_bounded_fields() -> None:
    values = fake_corpus()
    source = MessageInput(
        message_id="opaque-msg-001",
        sender="Alerts <" + values["email"] + ">",
        subject="Payment alert",
        snippet=f"Rs {values['amount']} debited; ref {values['reference']}",
        body_text=(
            f"PAN {values['pan']} account {values['account']} "
            f"and phone {values['phone']}. " + "body " * 500
        ),
        received_at="2026-01-02T10:00:00Z",
    )
    settings = LLMSettings(max_message_chars=180)
    prepared = build_provider_payload(source, settings)
    payload = prepared.payload
    serialized = json.dumps(payload.model_dump())

    for sensitive in (values["pan"], values["account"], values["phone"], values["email"]):
        assert sensitive not in serialized
    assert values["reference"] in serialized
    assert f"Rs {values['amount']}" in serialized
    text_fields = payload.subject + payload.snippet + payload.body_text
    assert len(text_fields) <= settings.max_message_chars
    assert "redactions" not in payload.model_dump()
    assert prepared.restore_quote("<PAN_1>") == values["pan"]


def test_payload_rejects_oauth_token_shaped_input() -> None:
    token = "ya29." + "a" * 32
    source = MessageInput(
        message_id="opaque-msg-002",
        sender="synthetic-sender",
        subject="Token test",
        snippet="safe",
        body_text=f"Authorization: Bearer {token}",
        received_at=None,
    )
    with pytest.raises(OAuthTokenDetected):
        build_provider_payload(source, LLMSettings(max_message_chars=100))


def test_payload_rejects_non_opaque_message_ids() -> None:
    source = MessageInput(
        message_id="user email" + "@example.invalid",
        sender="synthetic-sender",
        subject="safe",
        snippet="safe",
        body_text="safe",
        received_at=None,
    )
    with pytest.raises(ValueError, match="opaque"):
        build_provider_payload(source, LLMSettings(max_message_chars=100))


def test_llm_has_no_logging_calls_with_payload_or_body_arguments() -> None:
    forbidden_names = {"payload", "body", "body_text", "redacted_text"}
    log_methods = {"debug", "info", "warning", "error", "exception", "critical", "log"}
    for path in Path("llm").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in log_methods:
                continue
            names = {
                arg.id
                for arg in node.args
                if isinstance(arg, ast.Name)
            }
            assert not names & forbidden_names, f"possible payload/body log in {path}"
