import os
import yaml
import logging
from typing import List, Dict, Any, Optional

from config.settings import settings
from storage.engagement_db import EngagementDB
from scanner.post_extractor import parse_post_payload

logger = logging.getLogger(__name__)

class LinkedInScanner:
    """
    Discovers trending LinkedIn tech posts across configured keywords, hashtags, and watchlists.
    Supports Playwright session browsing, URL targeting, and mock candidate testing.
    """

    def __init__(self, db: Optional[EngagementDB] = None):
        self.db = db or EngagementDB()
        self.targets = self._load_targets()

    def _load_targets(self) -> Dict[str, Any]:
        """Loads target keywords and hashtags from targets.yaml."""
        targets_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            "targets.yaml"
        )
        if os.path.exists(targets_file):
            try:
                with open(targets_file, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except Exception as ex:
                logger.warning(f"Failed to load targets.yaml: {ex}")
        return {}

    def fetch_candidates(self, max_candidates: int = 5) -> List[Dict[str, Any]]:
        """
        Discovers candidate posts that have not yet been engaged.
        If LinkedIn session cookie is configured and Playwright is available,
        it scans live feeds. Otherwise, returns high-value simulated tech posts for review.
        """
        candidates: List[Dict[str, Any]] = []

        # If session cookie is missing or unconfigured, generate curated realistic tech candidates
        if not settings.linkedin_li_at or settings.linkedin_li_at.startswith("your_"):
            logger.info("ℹ️ LinkedIn session cookie (LINKEDIN_LI_AT) not configured. Using curated high-value AI discussion candidates.")
            candidates = self._get_curated_sample_candidates()
        else:
            try:
                candidates = self._scan_live_linkedin(max_candidates)
            except Exception as ex:
                logger.error(f"Live LinkedIn scan failed: {ex}. Falling back to sample candidates.")
                candidates = self._get_curated_sample_candidates()

            if not candidates:
                logger.info("ℹ️ Live scan returned 0 posts (session expired or selector mismatch). Falling back to curated sample candidates.")
                candidates = self._get_curated_sample_candidates()

        # Filter out already engaged posts
        unengaged = []
        for post in candidates:
            url = post.get("url", "")
            author = post.get("author_name", "")
            if self.db.is_post_already_engaged(url):
                logger.debug(f"Skipping already engaged post: {url}")
                continue
            if self.db.is_author_recently_engaged(author):
                logger.debug(f"Skipping post by recently engaged author ({author}): {url}")
                continue
            unengaged.append(post)
            if len(unengaged) >= max_candidates:
                break

        logger.info(f"Discovered {len(unengaged)} unengaged post candidate(s) ready for analysis.")
        return unengaged

    def scan_single_post(self, post_url: str, post_content: str, author_name: str = "Engineer") -> Dict[str, Any]:
        """Manually inspects a single post URL provided by the user."""
        return parse_post_payload(
            url=post_url,
            content=post_content,
            author_name=author_name,
            topic="Direct User Inspection"
        )

    def _scan_live_linkedin(self, max_candidates: int) -> List[Dict[str, Any]]:
        """Scrapes live posts via Playwright using stealth session cookie."""
        from playwright.sync_api import sync_playwright

        candidates = []
        keywords = self.targets.get("target_keywords", ["vLLM", "Agentic AI"])
        query = keywords[0]

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            # Add session cookie
            context.add_cookies([{
                "name": "li_at",
                "value": settings.linkedin_li_at,
                "domain": ".linkedin.com",
                "path": "/"
            }])

            page = context.new_page()
            search_url = f"https://www.linkedin.com/search/results/content/?keywords={query}&sortBy=%22date_posted%22"
            page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # Extract post containers
            posts_locators = page.locator(".feed-shared-update-v2").all()
            for loc in posts_locators[:max_candidates * 2]:
                try:
                    text = loc.locator(".feed-shared-update-v2__description").inner_text()
                    author = loc.locator(".update-components-actor__name").first.inner_text()
                    headline = loc.locator(".update-components-actor__description").first.inner_text()
                    urn = loc.get_attribute("data-urn") or ""
                    post_url = f"https://www.linkedin.com/feed/update/{urn}/" if urn else search_url

                    if text and len(text.strip()) > 60:
                        candidates.append(parse_post_payload(
                            url=post_url,
                            content=text,
                            author_name=author,
                            author_headline=headline,
                            urn=urn,
                            topic=query
                        ))
                except Exception:
                    continue

            browser.close()
        return candidates

    def _get_curated_sample_candidates(self) -> List[Dict[str, Any]]:
        """Provides realistic real-world tech posts for development, testing, and zero-setup demonstration."""
        return [
            parse_post_payload(
                url="https://www.linkedin.com/feed/update/urn:li:activity:7182938475618293841",
                content=(
                    "We just completed migrating our agentic multi-agent orchestrator from Python to Rust. "
                    "By eliminating Python's Global Interpreter Lock (GIL) and optimizing JSON state serialization "
                    "across 12 autonomous subagents, our end-to-end P99 response latency dropped from 2.4s to 480ms. "
                    "However, our developer iteration velocity took an initial hit because building rapid prototypes "
                    "with compile-time type checking in Rust is noticeably slower than quick Python scripts."
                ),
                author_name="Alex Rivera",
                author_headline="Staff AI Infrastructure Engineer @ HyperScale AI",
                topic="Multi-Agent Systems & Rust Migration"
            ),
            parse_post_payload(
                url="https://www.linkedin.com/feed/update/urn:li:activity:7182938475618293842",
                content=(
                    "Most developers building RAG are obsessing over the wrong metric. They spend weeks tuning chunk sizes "
                    "and vector embeddings (cosine vs dot product), but in production, 80% of our query failures were caused "
                    "by stale data synchronization and lack of document permission filtering. If your retrieval layer "
                    "doesn't support real-time ACL checks and hybrid lexical search (BM25 + Dense), pure semantic search "
                    "will hallucinate confident nonsense when user permissions vary."
                ),
                author_name="Sarah Chen",
                author_headline="VP of Engineering @ DataMesh Systems",
                topic="Production RAG & Vector Search"
            ),
            parse_post_payload(
                url="https://www.linkedin.com/feed/update/urn:li:activity:7182938475618293843",
                content=(
                    "Running vLLM in production with high concurrency: PagedAttention solved memory fragmentation, "
                    "but under bursty traffic with variable input prompt lengths (1k to 32k tokens), our GPU memory "
                    "is still bottlenecked by KV cache eviction overhead during continuous batching. "
                    "Has anyone had success implementing chunked prefill with speculative decoding on Llama 3 70B "
                    "without spiking TTFT (Time To First Token)?"
                ),
                author_name="Marcus Vance",
                author_headline="Lead ML Systems Architect @ CloudCore",
                topic="LLM Inference & vLLM Optimization"
            )
        ]
