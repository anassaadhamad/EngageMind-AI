import re
from typing import Dict, Any, Optional

def clean_linkedin_post_url(url: str) -> str:
    """Strips tracking query parameters and normalizes LinkedIn post URL."""
    if not url:
        return ""
    # Strip tracking params like ?utm_source, ?trackingId, etc.
    clean = url.split("?")[0].strip().rstrip("/")
    return clean

def extract_clean_snippet(text: str, max_chars: int = 400) -> str:
    """Normalizes whitespace and extracts an excerpt for review."""
    if not text:
        return ""
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_chars:
        return clean
    return clean[:max_chars - 3] + "..."

def parse_post_payload(
    url: str,
    content: str,
    author_name: str = "Unknown Author",
    author_headline: str = "",
    urn: Optional[str] = None,
    topic: str = "AI & Tech"
) -> Dict[str, Any]:
    """Formats standardized post candidate payload for EngageMind AI pipeline."""
    clean_url = clean_linkedin_post_url(url)
    return {
        "url": clean_url,
        "urn": urn or clean_url.split("/")[-1],
        "author_name": author_name.strip() or "Engineer",
        "author_headline": author_headline.strip(),
        "content": content.strip(),
        "snippet": extract_clean_snippet(content),
        "topic": topic
    }
