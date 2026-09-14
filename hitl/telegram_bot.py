import html
import json
import logging
import requests
from typing import Dict, Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

class TelegramEngagementBot:
    """
    Delivers real-time LinkedIn engagement opportunities to the user's private Telegram chat.
    Renders 3 distinct high-IQ comment perspectives with 1-click copy and direct post navigation.
    """

    BASE_URL = "https://api.telegram.org/bot"

    def __init__(self):
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id

    def send_opportunity_card(
        self,
        post_data: Dict[str, Any],
        ai_comments: Dict[str, str],
        analysis: str = ""
    ) -> bool:
        """
        Sends an interactive review card presenting the target post and 3 tailored comment options.
        """
        if not self.token or not self.chat_id or self.token.startswith("your_"):
            logger.info("ℹ️ Telegram credentials unconfigured. Printing opportunity card to console.")
            self._print_opportunity_to_console(post_data, ai_comments, analysis)
            return True

        author = html.escape(str(post_data.get("author_name", "Engineer")))
        headline = html.escape(str(post_data.get("author_headline", "Tech Lead")))
        topic = html.escape(str(post_data.get("topic", "AI & Architecture")))
        snippet = html.escape(str(post_data.get("snippet", "")))
        post_url = post_data.get("url", "https://linkedin.com")

        c_tradeoff = html.escape(str(ai_comments.get("tradeoff", "")))
        c_prod = html.escape(str(ai_comments.get("production", "")))
        c_socratic = html.escape(str(ai_comments.get("socratic", "")))

        card_text = (
            f"🎯 <b>EngageMind AI — رصد منشور تقني ساخن</b> 🔥\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>الكاتب:</b> <b>{author}</b>\n"
            f"💼 <i>{headline}</i>\n"
            f"📂 <b>الموضوع:</b> #{topic}\n\n"
            f"📝 <b>نبذة من المنشور:</b>\n"
            f"<i>\"{snippet}\"</i>\n\n"
            f"💡 <b>الخيارات المقترحة للتعليق (Senior Engineer):</b>\n\n"
            f"<b>[1] 🛠️ مقايضة معمارية (Trade-off):</b>\n"
            f"<code>{c_tradeoff}</code>\n\n"
            f"<b>[2] 🏢 تجربة إنتاجية (Production Edge Case):</b>\n"
            f"<code>{c_prod}</code>\n\n"
            f"<b>[3] ❓ سؤال فكري ونقاش (Socratic Question):</b>\n"
            f"<code>{c_socratic}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<i>💡 اضغط على أي رد بالأعلى لنسخه فوراً ولصقه في البوست.</i>"
        )

        inline_keyboard = [
            [
                {"text": "🔗 فتح البوست على LinkedIn", "url": post_url}
            ]
        ]

        # If in stealth mode, provide one-tap auto-post buttons
        if settings.operating_mode == "stealth":
            inline_keyboard.append([
                {"text": "🚀 نشر 1 آلياً", "callback_data": "post_1"},
                {"text": "🚀 نشر 2 آلياً", "callback_data": "post_2"},
                {"text": "🚀 نشر 3 آلياً", "callback_data": "post_3"}
            ])

        payload = {
            "chat_id": self.chat_id,
            "text": card_text,
            "parse_mode": "HTML",
            "reply_markup": json.dumps({"inline_keyboard": inline_keyboard})
        }

        try:
            url = f"{self.BASE_URL}{self.token}/sendMessage"
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                logger.info(f"Successfully delivered engagement card for post by '{author}'.")
                return True
            else:
                logger.error(f"Telegram sendMessage failed ({resp.status_code}): {resp.text}")
                return False
        except Exception as ex:
            logger.error(f"Telegram card dispatch exception: {ex}")
            return False

    def send_alert(self, text: str) -> bool:
        """Sends an urgent operational alert directly to admin."""
        if not self.token or not self.chat_id or self.token.startswith("your_"):
            logger.warning(f"ALERT: {text}")
            return False
        try:
            url = f"{self.BASE_URL}{self.token}/sendMessage"
            resp = requests.post(url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}, timeout=10)
            return resp.status_code == 200
        except Exception as ex:
            logger.error(f"Failed sending alert: {ex}")
            return False

    def _print_opportunity_to_console(
        self,
        post_data: Dict[str, Any],
        ai_comments: Dict[str, str],
        analysis: str
    ):
        """Clean CLI fallback when Telegram is not configured."""
        author = post_data.get("author_name", "Engineer")
        headline = post_data.get("author_headline", "")
        post_url = post_data.get("url", "")
        snippet = post_data.get("snippet", "")

        print("\n" + "=" * 70)
        print(f"🎯 ENGAGEMIND AI — NEW POST OPPORTUNITY")
        print(f"👤 Author: {author} ({headline})")
        print(f"🔗 URL: {post_url}")
        print(f"📝 Excerpt: {snippet[:200]}...")
        if analysis:
            print(f"🧠 Analysis: {analysis}")
        print("-" * 70)
        print("💡 [Option 1 - Architectural Trade-off]:")
        print(f"   {ai_comments.get('tradeoff')}")
        print("\n💡 [Option 2 - Production Experience]:")
        print(f"   {ai_comments.get('production')}")
        print("\n💡 [Option 3 - Socratic Question]:")
        print(f"   {ai_comments.get('socratic')}")
        print("=" * 70 + "\n")
