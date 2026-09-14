import time
import random
import logging
from typing import Tuple, Optional

from config.settings import settings
from storage.engagement_db import EngagementDB

logger = logging.getLogger(__name__)

class HumanDispatcher:
    """
    Simulates human behavior for typing and posting comments.
    Enforces keystroke jitter (45ms - 140ms), punctuation pauses, and emergency circuit breakers.
    """

    def __init__(self, db: Optional[EngagementDB] = None):
        self.db = db or EngagementDB()

    def simulate_human_typing(self, page, element_locator, text: str) -> None:
        """
        Types text character-by-character with realistic typing jitter and micro-hesitations.
        """
        element_locator.click()
        time.sleep(random.uniform(0.3, 0.7))

        min_ms = settings.typing_delay_min_ms / 1000.0
        max_ms = settings.typing_delay_max_ms / 1000.0

        for char in text:
            element_locator.type(char, delay=int(random.uniform(min_ms, max_ms) * 1000))
            # Micro-hesitation after punctuation marks
            if char in [".", ",", "?", "!"]:
                time.sleep(random.uniform(0.15, 0.35))
            # Rare random thinking pause (2% probability)
            elif random.random() < 0.02:
                time.sleep(random.uniform(0.4, 0.8))

        time.sleep(random.uniform(0.5, 1.2))

    def check_for_security_checkpoint(self, page) -> Tuple[bool, str]:
        """
        Circuit Breaker: Scans page for LinkedIn security verification challenges
        (Captcha, phone verification, pin prompt, checkpoint URL).
        Returns (is_checkpoint_active, details).
        """
        try:
            current_url = page.url.lower()
            if "checkpoint" in current_url or "challenge" in current_url:
                return True, f"Security challenge detected in URL: {current_url}"

            body_text = page.inner_text("body").lower()
            checkpoint_triggers = [
                "security verification", "verify your identity",
                "quick security check", "enter the code sent to",
                "unusual activity"
            ]
            for trigger in checkpoint_triggers:
                if trigger in body_text:
                    return True, f"Security challenge prompt detected: '{trigger}'"

        except Exception as ex:
            logger.debug(f"Error checking for checkpoint: {ex}")

        return False, "No security challenge detected."

    def post_comment_stealth(
        self,
        post_url: str,
        comment_text: str,
        author_name: str,
        selected_style: str = "tradeoff"
    ) -> Tuple[bool, str]:
        """
        Executes stealth commenting via Playwright.
        Validates safety quotas, navigates to post, checks for security checkpoints,
        simulates typing, submits, and records in database.
        """
        # 1. Strict Pre-flight Safety Gate
        allowed, reason = self.db.can_engage_now()
        if not allowed:
            logger.warning(f"🚫 Stealth posting blocked by safety policy: {reason}")
            return False, reason

        if not settings.linkedin_li_at or settings.linkedin_li_at.startswith("your_"):
            return False, "LINKEDIN_LI_AT cookie is required for stealth posting mode."

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            context.add_cookies([{
                "name": "li_at",
                "value": settings.linkedin_li_at,
                "domain": ".www.linkedin.com",
                "path": "/"
            }])

            page = context.new_page()
            logger.info(f"Navigating to post: {post_url}")
            page.goto(post_url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2.0, 3.5))

            # 2. Circuit Breaker Check
            is_checkpoint, cp_reason = self.check_for_security_checkpoint(page)
            if is_checkpoint:
                logger.critical(f"🚨 CIRCUIT BREAKER TRIPPED: {cp_reason}! Aborting immediately.")
                browser.close()
                return False, f"CIRCUIT BREAKER: {cp_reason}"

            # 3. Locate Comment Box
            try:
                # Open comment box if needed
                comment_button = page.locator("button.comment-button, button[aria-label*='Comment']").first
                if comment_button.is_visible():
                    comment_button.click()
                    time.sleep(random.uniform(0.8, 1.5))

                editor = page.locator("div.ql-editor, div[role='textbox']").first
                if not editor.is_visible():
                    browser.close()
                    return False, "Could not locate comment text editor on post page."

                # 4. Human Typing
                logger.info(f"Typing comment ({len(comment_text)} chars) with human keystroke jitter...")
                self.simulate_human_typing(page, editor, comment_text)

                # 5. Submit Comment
                submit_btn = page.locator("button.comments-comment-box__submit-button, button.comments-comment-box__submit-button--enabled").first
                if submit_btn.is_visible() and submit_btn.is_enabled():
                    time.sleep(random.uniform(0.5, 1.2))
                    submit_btn.click()
                    time.sleep(random.uniform(2.0, 3.5))
                    logger.info("🎉 Comment submitted successfully to LinkedIn!")

                    # 6. Record in Database
                    self.db.record_engagement(
                        post_url=post_url,
                        author_name=author_name,
                        comment_text=comment_text,
                        selected_style=selected_style,
                        mode="stealth",
                        status="POSTED"
                    )
                    browser.close()
                    return True, "Comment successfully posted via stealth engine."
                else:
                    browser.close()
                    return False, "Submit button not enabled after typing."

            except Exception as ex:
                browser.close()
                logger.error(f"Error during stealth comment dispatch: {ex}")
                return False, str(ex)
