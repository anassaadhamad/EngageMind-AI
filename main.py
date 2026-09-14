import sys
import argparse
import logging

# Set UTF-8 encoding for Windows terminal
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("EngageMindAI")

from config.settings import settings
from storage.engagement_db import EngagementDB
from scanner.linkedin_scanner import LinkedInScanner
from brain.comment_generator import CommentGenerator
from hitl.telegram_bot import TelegramEngagementBot

def run_discovery_cycle(limit: int = 3, force: bool = False):
    """
    Executes a complete discovery & engagement cycle:
    1. Validates safety policies (working hours, daily quota, cooldown).
    2. Scans for candidate posts across target topics.
    3. Synthesizes 3 High-IQ comment options via Claude / Gemini.
    4. Delivers interactive cards to Telegram studio with 1-click copy & navigation.
    """
    db = EngagementDB()
    telegram_bot = TelegramEngagementBot()

    # Safety Gate Check
    allowed, reason = db.can_engage_now()
    if not allowed and not force:
        logger.warning(f"⏸️ Engagement skipped by safety policy: {reason}")
        return

    logger.info("1️⃣ Scanning LinkedIn for high-value tech discussion opportunities...")
    scanner = LinkedInScanner(db=db)
    candidates = scanner.fetch_candidates(max_candidates=limit)

    if not candidates:
        logger.info("No new unengaged candidates found at this time.")
        return

    logger.info(f"2️⃣ Processing {len(candidates)} candidate post(s) through AI Brain...")
    generator = CommentGenerator()

    for idx, post in enumerate(candidates, 1):
        author = post.get("author_name", "Engineer")
        url = post.get("url", "")
        content = post.get("content", "")
        topic = post.get("topic", "AI Architecture")

        logger.info(f"[{idx}/{len(candidates)}] Generating comments for post by '{author}' ({topic})...")
        result = generator.generate_comments_for_post(
            post_content=content,
            author_name=author,
            author_headline=post.get("author_headline", ""),
            topic=topic
        )

        if not result or "comments" not in result:
            logger.warning(f"Could not generate valid comments for post: {url}")
            continue

        comments = result.get("comments", {})
        analysis = result.get("analysis", "")

        # Deliver to Telegram Studio
        logger.info(f"Delivering opportunity card to Telegram...")
        telegram_bot.send_opportunity_card(
            post_data=post,
            ai_comments=comments,
            analysis=analysis
        )

        # Record candidate in DB as COPIED / PENDING
        db.record_engagement(
            post_url=url,
            author_name=author,
            comment_text=comments.get("tradeoff", ""),
            selected_style="tradeoff",
            author_headline=post.get("author_headline", ""),
            post_snippet=post.get("snippet", ""),
            mode=settings.operating_mode,
            status="COPIED"
        )

    # Show updated stats
    stats = db.get_stats_today()
    logger.info(f"📊 Daily Activity: {stats['comments_count']}/{stats['max_allowed']} comments engaged today ({stats['remaining']} remaining).")

def inspect_single_post(url: str, text: str, author: str = "Engineer"):
    """CLI tool to inspect and generate 3 comments for any given post text."""
    logger.info(f"Analyzing post by '{author}'...")
    generator = CommentGenerator()
    result = generator.generate_comments_for_post(post_content=text, author_name=author)
    if result:
        telegram_bot = TelegramEngagementBot()
        post_data = {
            "author_name": author,
            "author_headline": "Inspected via CLI",
            "url": url,
            "snippet": text[:300],
            "topic": "Manual Review"
        }
        telegram_bot.send_opportunity_card(post_data, result.get("comments", {}), result.get("analysis", ""))
    else:
        logger.error("Failed to generate comments.")

def print_stats():
    """Prints today's engagement quota and status."""
    db = EngagementDB()
    stats = db.get_stats_today()
    allowed, reason = db.can_engage_now()
    print("\n" + "=" * 50)
    print("📊 ENGAGEMIND AI — DAILY ENGAGEMENT STATUS")
    print("=" * 50)
    print(f"📅 Date: {stats['date']}")
    print(f"💬 Comments Used Today: {stats['comments_count']} / {stats['max_allowed']}")
    print(f"🎯 Remaining Allowance: {stats['remaining']}")
    print(f"⏱️ Last Comment At: {stats['last_comment_at'] or 'None today'}")
    print(f"🛡️ Safety Gate Status: {'🟢 PERMITTED' if allowed else '🔴 BLOCKED'}")
    print(f"ℹ️ Reason: {reason}")
    print("=" * 50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="EngageMind AI — Autonomous LinkedIn AI Engagement & Inbound Growth Copilot")
    parser.add_argument("--discover", action="store_true", help="Run discovery and generate comments for new posts")
    parser.add_argument("--limit", type=int, default=3, help="Max candidate posts to process")
    parser.add_argument("--force", action="store_true", help="Bypass safety hours check for testing")
    parser.add_argument("--stats", action="store_true", help="Display today's engagement stats and safety quota")
    parser.add_argument("--test", action="store_true", help="Run a dry-run test discovery cycle")

    args = parser.parse_args()

    if args.stats:
        print_stats()
    elif args.test or args.discover:
        run_discovery_cycle(limit=args.limit, force=args.force or args.test)
    else:
        # Default behavior: run test discovery
        print_stats()
        run_discovery_cycle(limit=args.limit, force=True)

if __name__ == "__main__":
    main()
