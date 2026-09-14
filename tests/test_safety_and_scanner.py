import pytest
from scanner.post_extractor import clean_linkedin_post_url, extract_clean_snippet, parse_post_payload
from poster.human_dispatcher import HumanDispatcher

def test_url_normalization():
    dirty_url = "https://www.linkedin.com/feed/update/urn:li:activity:7182938475618293841/?utm_source=share&utm_medium=member_desktop&rcm=ACoAA"
    clean = clean_linkedin_post_url(dirty_url)
    assert clean == "https://www.linkedin.com/feed/update/urn:li:activity:7182938475618293841"

def test_extract_clean_snippet():
    raw_text = "   This is a post    with multiple     spaces \n\n and newlines.   "
    snippet = extract_clean_snippet(raw_text, max_chars=50)
    assert snippet == "This is a post with multiple spaces and newlines."
    assert "   " not in snippet

def test_security_checkpoint_detection():
    dispatcher = HumanDispatcher()

    class MockCheckpointPage:
        url = "https://www.linkedin.com/checkpoint/challenge/AgF..."
        def inner_text(self, selector):
            return "Please enter the verification code sent to your phone"

    class MockSafePage:
        url = "https://www.linkedin.com/feed/update/urn:li:activity:123"
        def inner_text(self, selector):
            return "Just launched our new open-source LLM inference library!"

    is_cp, reason = dispatcher.check_for_security_checkpoint(MockCheckpointPage())
    assert is_cp is True
    assert "Security challenge" in reason

    is_safe_cp, _ = dispatcher.check_for_security_checkpoint(MockSafePage())
    assert is_safe_cp is False

def test_parse_post_payload_structure():
    payload = parse_post_payload(
        url="https://linkedin.com/feed/update/123",
        content="Testing distributed training workloads.",
        author_name="Alice Smith",
        author_headline="Principal Engineer",
        topic="Distributed Systems"
    )
    assert payload["author_name"] == "Alice Smith"
    assert payload["topic"] == "Distributed Systems"
    assert "Testing distributed" in payload["snippet"]
