"""RSS Feed 解析器"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta

import feedparser

from ..models import Article, ArticleSource


def _parse_time(entry: dict) -> str:
    """从 feedparser entry 中提取发布时间字符串"""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return dt.isoformat()
    return datetime.now(timezone.utc).isoformat()


def _is_recent(published_at: str, max_age_hours: int) -> bool:
    """判断文章是否在 max_age_hours 小时内"""
    try:
        pub_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        return pub_dt >= cutoff
    except (ValueError, TypeError):
        return True  # 解析失败则保留


def _make_article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def fetch_rss_articles(feeds: list[dict], max_age_hours: int = 48) -> tuple[Article, ...]:
    """
    解析多个 RSS feeds，返回最近 max_age_hours 内的文章。

    Args:
        feeds: list of {"name": str, "url": str, "lang": str}
        max_age_hours: 只保留此时间窗口内的文章

    Returns:
        tuple[Article, ...] 按发布时间倒序
    """
    articles: list[Article] = []

    for feed_config in feeds:
        feed_url = feed_config["url"]
        feed_name = feed_config.get("name", feed_url)
        lang = feed_config.get("lang", "en")

        try:
            parsed = feedparser.parse(feed_url)
        except Exception as exc:
            print(f"[RSS] 解析失败 {feed_name}: {exc}")
            continue

        for entry in parsed.entries:
            url = getattr(entry, "link", "")
            if not url:
                continue

            title = getattr(entry, "title", "").strip()
            summary = (
                getattr(entry, "summary", "")
                or getattr(entry, "description", "")
            ).strip()
            # 截断过长摘要
            if len(summary) > 500:
                summary = summary[:500] + "..."

            published_at = _parse_time(entry)

            if not _is_recent(published_at, max_age_hours):
                continue

            articles.append(Article(
                id=_make_article_id(url),
                title=title,
                url=url,
                source=ArticleSource.RSS,
                source_name=feed_name,
                summary=summary,
                language=lang,
                published_at=published_at,
            ))

    # 按发布时间倒序
    articles.sort(key=lambda a: a.published_at, reverse=True)
    return tuple(articles)
