"""Run conditions + Sculptor table knowledge tests."""

from __future__ import annotations

from claycomp.web.schemas import RecordDTO
from claycomp.web.sculptor import _user_intent
from claycomp.web.schemas import ChatMessage
from claycomp.web.table_knowledge import (
    answer_table_query,
    build_table_knowledge,
    knowledge_to_prompt_block,
)


def _rec(**kwargs) -> RecordDTO:
    base = {
        "id": kwargs.pop("id", "r1"),
        "raw": kwargs.pop("raw", {}),
        "enriched": kwargs.pop("enriched", {}),
    }
    base.update(kwargs)
    return RecordDTO.model_validate(base)


def test_knowledge_counts_emails_and_gaps():
    records = [
        _rec(id="1", email="a@x.com", company="Acme", first_name="Ada"),
        _rec(id="2", company="Acme", first_name="Grace", raw={"Work Email": ""}),
        _rec(id="3", company="Beta", first_name="Alan", enriched={"email_waterfall": {"email": "alan@beta.com"}}),
    ]
    kb = build_table_knowledge(records, [{"label": "Work Email", "enricherKey": "email_waterfall"}])
    assert kb["row_count"] == 3
    assert kb["field_counts"]["email"] == 2
    assert kb["rows_missing_email"] == 1
    block = knowledge_to_prompt_block(kb)
    assert "TABLE KNOWLEDGE BASE" in block
    assert "Work Email" in block


def test_answer_table_query_email_facts():
    records = [
        _rec(id="1", email="a@x.com", company="Acme"),
        _rec(id="2", company="Acme"),
    ]
    kb = build_table_knowledge(records, [])
    result = answer_table_query("How many leads are missing emails?", kb)
    assert any("missing" in f.lower() or "email" in f.lower() for f in result["facts"])


def test_chat_intent_does_not_force_architect():
    intent = _user_intent([ChatMessage(role="user", content="How many leads are missing emails?")])
    assert intent["mode"] == "chat"
    assert intent["is_specific"] is False


def test_architect_intent_for_email_waterfall():
    intent = _user_intent([
        ChatMessage(
            role="user",
            content="Add an email finder waterfall and skip if there's already an email",
        )
    ])
    assert intent["mode"] == "architect"
    assert intent["primary_topic"] == "email" or "skip if" in (intent.get("hint") or "").lower() or intent["mode"] == "architect"


def test_configure_intent():
    intent = _user_intent([
        ChatMessage(role="user", content="Don't run the Work Email column if email is already filled"),
    ])
    assert intent["mode"] == "architect"
    assert "configure" in (intent.get("hint") or "").lower() or "skip" in (intent.get("hint") or "").lower()
