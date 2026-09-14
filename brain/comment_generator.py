import json
import logging
import re
import requests
from typing import Dict, Any, Optional

from config.settings import settings
from brain.prompt_templates import ENGAGEMENT_SYSTEM_PROMPT, ENGAGEMENT_USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

BANNED_OPENERS = [
    "great post", "thanks for sharing", "couldn't agree more", "spot on",
    "totally agree", "super interesting", "exciting times", "love this",
    "awesome read", "kudos", "well said"
]

class CommentGenerator:
    """
    Synthesizes High-IQ LinkedIn comments tailored for senior technical audiences.
    Supports Anthropic Claude direct or OpenRouter fallback.
    """

    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self.anthropic_key = settings.anthropic_api_key
        self.openrouter_key = settings.openrouter_api_key

    def generate_comments_for_post(
        self,
        post_content: str,
        author_name: str = "Engineer",
        author_headline: str = "Tech Lead",
        topic: str = "AI & Software Engineering"
    ) -> Optional[Dict[str, Any]]:
        """
        Generates 3 distinct high-IQ comment perspectives for a target post.
        Returns parsed dict or None if generation failed.
        """
        if not post_content or len(post_content.strip()) < 30:
            logger.warning("Post content too short to generate meaningful technical comments.")
            return None

        # Clean snippet (truncate to 2500 chars to conserve tokens)
        clean_content = post_content[:2500].strip()

        user_prompt = ENGAGEMENT_USER_PROMPT_TEMPLATE.format(
            author_name=author_name,
            author_headline=author_headline,
            topic=topic,
            post_content=clean_content
        )

        raw_response = None

        # Priority 1: Direct Anthropic if key provided or provider set
        if (self.provider in ["anthropic", "auto"]) and self.anthropic_key and not self.anthropic_key.startswith("your_"):
            try:
                raw_response = self._call_anthropic(user_prompt)
            except Exception as ex:
                logger.warning(f"Anthropic direct call failed: {ex}. Attempting fallback...")

        # Priority 2: OpenRouter if Anthropic failed or configured
        if not raw_response and self.openrouter_key and not self.openrouter_key.startswith("your_"):
            try:
                raw_response = self._call_openrouter(user_prompt)
            except Exception as ex:
                logger.error(f"OpenRouter call failed: {ex}")

        if not raw_response:
            logger.error("No LLM provider succeeded in generating comments.")
            return None

        # Parse & Validate JSON
        parsed = self._clean_and_parse_json(raw_response)
        if not parsed or "comments" not in parsed:
            logger.error(f"Failed to parse LLM JSON: {raw_response[:200]}")
            return None

        # Sanitize comments to strictly ensure no generic fluff escaped
        comments = parsed.get("comments", {})
        for style, text in comments.items():
            comments[style] = self._sanitize_comment(text)

        parsed["comments"] = comments
        return parsed

    def _call_anthropic(self, user_prompt: str) -> str:
        """Calls Anthropic Claude API directly."""
        import anthropic
        client = anthropic.Anthropic(api_key=self.anthropic_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1000,
            temperature=0.7,
            system=ENGAGEMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return response.content[0].text

    def _call_openrouter(self, user_prompt: str) -> str:
        """Calls OpenRouter endpoint with Claude / Gemini model."""
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "HTTP-Referer": "https://github.com/anassaadhamad/EngageMind-AI",
            "X-Title": "EngageMind AI",
            "Content-Type": "application/json"
        }
        payload = {
            "model": settings.openrouter_model,
            "messages": [
                {"role": "system", "content": ENGAGEMENT_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"}
        }
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            raise ValueError(f"OpenRouter HTTP {resp.status_code}: {resp.text}")

    def _clean_and_parse_json(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Strips markdown fences and parses JSON safely."""
        text = raw_text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fallback: regex search for outer JSON object
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except Exception:
                    pass
        return None

    def _sanitize_comment(self, text: str) -> str:
        """Removes em-dashes and strips banned opening cliches if present."""
        cleaned = text.replace("—", "-").replace("–", "-").strip()
        cleaned = cleaned.strip('"\'')

        pattern = r"^(?:great post|thanks for sharing|couldn't agree more|spot on|totally agree|super interesting|exciting times|love this|awesome read|kudos|well said)[!.,\s]*"
        while True:
            new_cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
            if new_cleaned == cleaned:
                break
            cleaned = new_cleaned

        return cleaned
