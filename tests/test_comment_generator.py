import pytest
from brain.comment_generator import CommentGenerator

def test_json_clean_and_parse():
    gen = CommentGenerator()

    raw_markdown_json = """
    ```json
    {
      "analysis": "The author discusses moving orchestrator to Rust for latency gains.",
      "comments": {
        "tradeoff": "Interesting shift. While Rust eliminates GIL bottlenecks, developer velocity is the real trade-off.",
        "production": "In our setup, memory fragmentation under variable batch sizes was the hidden challenge.",
        "socratic": "Did you benchmark against an async uvloop setup before committing to the rewrite?"
      }
    }
    ```
    """

    parsed = gen._clean_and_parse_json(raw_markdown_json)
    assert parsed is not None
    assert "comments" in parsed
    assert "tradeoff" in parsed["comments"]
    assert "production" in parsed["comments"]
    assert "socratic" in parsed["comments"]

def test_sanitize_banned_cliches_and_em_dash():
    gen = CommentGenerator()

    dirty_comment = "Great post! Thanks for sharing. We noticed that memory fragmentation—under variable load—is critical."
    cleaned = gen._sanitize_comment(dirty_comment)

    assert not cleaned.lower().startswith("great post")
    assert not cleaned.lower().startswith("thanks for sharing")
    assert "—" not in cleaned
    assert "-" in cleaned

def test_reject_too_short_content():
    gen = CommentGenerator()
    result = gen.generate_comments_for_post("Too short")
    assert result is None
