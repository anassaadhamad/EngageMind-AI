import os
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class EngageMindSettings(BaseModel):
    """Configuration and safety settings for EngageMind AI."""

    # 1. Operating Mode: 'copilot' (100% safe, Telegram cards with copy button) or 'stealth' (Playwright auto-posting)
    operating_mode: str = os.getenv("ENGAGEMIND_MODE", "copilot")

    # 2. AI Model & API Configuration
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    anthropic_model: str = os.getenv("ENGAGEMIND_ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")
    openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    openrouter_model: str = os.getenv("ENGAGEMIND_OPENROUTER_MODEL", "anthropic/claude-3.7-sonnet")
    llm_provider: str = os.getenv("ENGAGEMIND_LLM_PROVIDER", "auto")

    # 3. Telegram HITL Notification Studio
    telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = os.getenv("TELEGRAM_CHAT_ID")

    # 4. LinkedIn Session Authentication (Personal session cookie li_at)
    linkedin_li_at: Optional[str] = os.getenv("LINKEDIN_LI_AT")

    # 5. Strict Anti-Ban Safety Limits
    max_comments_per_day: int = int(os.getenv("ENGAGEMIND_MAX_COMMENTS_PER_DAY", "4"))
    min_cooldown_minutes: int = int(os.getenv("ENGAGEMIND_MIN_COOLDOWN_MINUTES", "60"))
    active_hours_start: int = int(os.getenv("ENGAGEMIND_ACTIVE_HOURS_START", "9")) # 09:00 AM
    active_hours_end: int = int(os.getenv("ENGAGEMIND_ACTIVE_HOURS_END", "19"))     # 07:00 PM
    timezone: str = os.getenv("TIMEZONE", "Africa/Cairo")

    # 6. Human Behavior & Keystroke Jitter (in milliseconds)
    typing_delay_min_ms: int = int(os.getenv("ENGAGEMIND_TYPING_DELAY_MIN_MS", "45"))
    typing_delay_max_ms: int = int(os.getenv("ENGAGEMIND_TYPING_DELAY_MAX_MS", "140"))

    # 7. Database Path
    db_path: str = os.getenv(
        "ENGAGEMIND_DB_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "storage", "engagemind.db")
    )

settings = EngageMindSettings()
