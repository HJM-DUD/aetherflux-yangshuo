"""Login-state browser collectors for public visible platform content.

The collectors connect to a user-opened Chrome DevTools endpoint. They do not
read cookie files, bypass captchas, or access private/non-visible content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol
from urllib.parse import quote

from .collector_model import plan_keyframe_offsets, select_comment_samples


class BrowserConnectionError(RuntimeError):
    pass


class BrowserSession(Protocol):
    def goto(self, url: str) -> None:
        ...

    def extract_cards(self, platform: str, max_items: int) -> List[Dict[str, Any]]:
        ...

    def extract_detail(self, url: str, platform: str, max_comments: int) -> Dict[str, Any]:
        ...

    def close(self) -> None:
        ...


@dataclass
class FakeBrowserSession:
    cards: List[Dict[str, Any]]
    details_by_url: Dict[str, Dict[str, Any]] | None = None
    visited_urls: List[str] | None = None

    def __post_init__(self) -> None:
        if self.visited_urls is None:
            self.visited_urls = []

    def goto(self, url: str) -> None:
        self.visited_urls.append(url)

    def extract_cards(self, platform: str, max_items: int) -> List[Dict[str, Any]]:
        return [dict(card) for card in self.cards[:max_items]]

    def extract_detail(self, url: str, platform: str, max_comments: int) -> Dict[str, Any]:
        if not self.details_by_url:
            return {}
        return dict(self.details_by_url.get(url, {}))

    def close(self) -> None:
        return None


class PlaywrightCDPSession:
    def __init__(self, cdp_url: str, wait_ms: int = 3500) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # pragma: no cover - environment dependent
            raise BrowserConnectionError("Playwright is required for live browser collection.") from exc

        self._sync_playwright = sync_playwright
        self._playwright = None
        self._browser = None
        self._page = None
        self.wait_ms = wait_ms
        try:
            self._playwright = self._sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(cdp_url)
            context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            self._page = context.new_page()
        except Exception as exc:
            self.close()
            raise BrowserConnectionError(
                "Cannot connect to Chrome remote debugging. Start Chrome with "
                "--remote-debugging-port=9222 and pass --cdp-url http://127.0.0.1:9222."
            ) from exc

    def goto(self, url: str) -> None:
        self._page.goto(url, wait_until="domcontentloaded", timeout=45000)
        self._page.wait_for_timeout(self.wait_ms)

    def extract_cards(self, platform: str, max_items: int) -> List[Dict[str, Any]]:
        return self._page.evaluate(_EXTRACT_CARDS_JS, {"platform": platform, "maxItems": max_items})

    def extract_detail(self, url: str, platform: str, max_comments: int) -> Dict[str, Any]:
        self.goto(url)
        return self._page.evaluate(_EXTRACT_DETAIL_JS, {"platform": platform, "maxComments": max_comments})

    def close(self) -> None:
        try:
            if self._page:
                self._page.close()
        finally:
            try:
                if self._browser:
                    self._browser.close()
            finally:
                if self._playwright:
                    self._playwright.stop()


class LivePlatformCollector:
    platform = ""
    search_url_template = ""

    def __init__(self, session: BrowserSession) -> None:
        self.session = session

    def search(self, query: str, cluster_id: str = "manual", max_items: int = 30, detail_limit: int = 5) -> List[Dict[str, Any]]:
        self.session.goto(self.search_url(query))
        cards = self.session.extract_cards(self.platform, max_items)
        items = []
        for index, card in enumerate(cards):
            if not (card.get("url") or card.get("title") or card.get("body")):
                continue
            enriched = dict(card)
            if index < detail_limit and card.get("url"):
                detail = self.session.extract_detail(str(card["url"]), self.platform, max_comments=30)
                enriched.update({key: value for key, value in detail.items() if value not in (None, "", [])})
            items.append(normalize_live_item(enriched, platform=self.platform, query=query, cluster_id=cluster_id))
        return items

    def search_url(self, query: str) -> str:
        return self.search_url_template.format(query=quote(query))


class XiaohongshuLiveCollector(LivePlatformCollector):
    platform = "xiaohongshu"
    search_url_template = "https://www.xiaohongshu.com/search_result?keyword={query}"


class DouyinLiveCollector(LivePlatformCollector):
    platform = "douyin"
    search_url_template = "https://www.douyin.com/search/{query}?type=general"


def collect_live_platform(
    platform: str,
    query: str,
    cdp_url: str = "http://127.0.0.1:9222",
    max_items: int = 30,
    cluster_id: str = "manual",
    detail_limit: int = 5,
    session: Optional[BrowserSession] = None,
) -> List[Dict[str, Any]]:
    owned_session = session is None
    browser_session = session or PlaywrightCDPSession(cdp_url)
    try:
        collector = _collector_for(platform, browser_session)
        return collector.search(query=query, cluster_id=cluster_id, max_items=max_items, detail_limit=detail_limit)
    finally:
        if owned_session:
            browser_session.close()


def normalize_live_item(card: Mapping[str, Any], platform: str, query: str, cluster_id: str) -> Dict[str, Any]:
    comments = select_comment_samples(card.get("comments_sample", []), keywords=["排队", "宰客", "投诉", "价格", "避雷", "推荐"])
    duration = _to_int(card.get("duration_seconds"))
    return {
        "title": _clean(card.get("title")) or _clean(card.get("body"))[:60] or "未命名视频情报",
        "body": _clean(card.get("body")),
        "source": f"{platform} live browser",
        "platform": platform,
        "url": _clean(card.get("url")),
        "published_at": _clean(card.get("published_at")),
        "author": _clean(card.get("author")),
        "content_type": "video" if card.get("has_video") or platform == "douyin" else "mixed",
        "engagement": {
            "likes": _to_int(card.get("likes")),
            "comments": _to_int(card.get("comments")),
            "shares": _to_int(card.get("shares")),
            "collects": _to_int(card.get("collects")),
        },
        "media": {
            "cover_url": _clean(card.get("cover_url")),
            "duration_seconds": duration,
            "planned_keyframes": plan_keyframe_offsets(duration) if duration else [],
        },
        "comments": comments,
        "query": query,
        "cluster_id": cluster_id,
        "capture_method": "chrome_cdp_login_state",
    }


def _collector_for(platform: str, session: BrowserSession) -> LivePlatformCollector:
    if platform == "xiaohongshu":
        return XiaohongshuLiveCollector(session)
    if platform == "douyin":
        return DouyinLiveCollector(session)
    raise ValueError(f"Unsupported live platform: {platform}")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _to_int(value: Any) -> int:
    try:
        text = str(value or "0").replace(",", "").strip()
        if text.endswith("万"):
            return int(float(text[:-1]) * 10000)
        return int(float(text))
    except (TypeError, ValueError):
        return 0


_EXTRACT_CARDS_JS = """
({ platform, maxItems }) => {
  const domainNeedle = platform === 'douyin' ? 'douyin.com' : 'xiaohongshu.com';
  const anchors = Array.from(document.querySelectorAll('a[href]'));
  const seen = new Set();
  const cards = [];

  function textOf(node) {
    return (node && node.innerText ? node.innerText : '').replace(/\\s+/g, ' ').trim();
  }

  function closestCard(anchor) {
    return anchor.closest('article, section, div[class*="card"], div[class*="note"], div[class*="feed"], div[class*="video"]') || anchor;
  }

  for (const anchor of anchors) {
    const href = anchor.href || '';
    if (!href.includes(domainNeedle)) continue;
    const normalized = href.split('?')[0];
    if (seen.has(normalized)) continue;
    const card = closestCard(anchor);
    const text = textOf(card) || textOf(anchor);
    if (!text || text.length < 4) continue;
    seen.add(normalized);
    const image = card.querySelector('img');
    const video = card.querySelector('video');
    const lines = text.split(' ').filter(Boolean);
    cards.push({
      title: lines[0] || '',
      body: text,
      url: normalized,
      author: '',
      likes: '',
      comments: '',
      shares: '',
      has_video: Boolean(video) || href.includes('/video/'),
      cover_url: image ? (image.currentSrc || image.src || '') : '',
      comments_sample: []
    });
    if (cards.length >= maxItems) break;
  }
  return cards;
}
"""

_EXTRACT_DETAIL_JS = """
({ platform, maxComments }) => {
  function clean(text) {
    return (text || '').replace(/\\s+/g, ' ').trim();
  }
  const body = clean(document.body ? document.body.innerText : '');
  const images = Array.from(document.querySelectorAll('img')).map((img) => img.currentSrc || img.src || '').filter(Boolean);
  const videos = Array.from(document.querySelectorAll('video'));
  const commentCandidates = Array.from(document.querySelectorAll('[class*="comment"], [data-e2e*="comment"], li, p, span'))
    .map((node, index) => ({ id: `visible-${index}`, text: clean(node.innerText || node.textContent || ''), likes: 0 }))
    .filter((item) => item.text.length >= 4 && item.text.length <= 240)
    .slice(0, maxComments);
  return {
    body,
    has_video: videos.length > 0,
    cover_url: images[0] || '',
    comments_sample: commentCandidates,
  };
}
"""
