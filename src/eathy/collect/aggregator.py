"""信息聚合器 — 合并 RSS + NewsAPI，去重，过滤已发布"""

from __future__ import annotations

import json
from pathlib import Path

from .rss import fetch_rss_articles
from .news import fetch_news_articles
from ..models import Article


def _load_published_ids(history_file: Path) -> set[str]:
    """加载已发布的文章 ID 集合（用于去重）"""
    if not history_file.exists():
        return set()
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
        return {entry["article_id"] for entry in data if "article_id" in entry}
    except (json.JSONDecodeError, KeyError):
        return set()


async def collect_all(config: dict, history_file: Path | None = None) -> tuple[Article, ...]:
    """
    聚合所有信息源，去重后返回候选文章列表。

    Args:
        config: 完整配置字典（load_config 返回值）
        history_file: 历史记录文件路径（用于去重，可为 None）

    Returns:
        tuple[Article, ...] 去重后，按时间倒序，最多 max_candidates 条
    """
    collect_cfg = config.get("collect", {})
    filter_cfg = config.get("filter", {})
    max_age_hours = collect_cfg.get("max_age_hours", 48)
    max_candidates = filter_cfg.get("max_candidates", 15)

    # 采集 RSS
    rss_feeds = collect_cfg.get("rss_feeds", [])
    rss_articles = fetch_rss_articles(rss_feeds, max_age_hours)

    # 采集 NewsAPI
    news_cfg = collect_cfg.get("news_api", {})
    news_api_key = news_cfg.get("api_key", "")
    news_articles: tuple[Article, ...] = ()
    if news_api_key:
        news_articles = await fetch_news_articles(
            api_key=news_api_key,
            queries=news_cfg.get("queries", []),
            max_age_hours=max_age_hours,
            max_results=news_cfg.get("max_results", 20),
        )

    # 合并去重（按 URL）
    seen_ids: set[str] = set()
    all_articles: list[Article] = []
    for article in (*rss_articles, *news_articles):
        if article.id not in seen_ids:
            seen_ids.add(article.id)
            all_articles.append(article)

    # 过滤已发布
    if history_file:
        published_ids = _load_published_ids(history_file)
        all_articles = [a for a in all_articles if a.id not in published_ids]

    # 按时间倒序，截断到 max_candidates
    all_articles.sort(key=lambda a: a.published_at, reverse=True)
    return tuple(all_articles[:max_candidates])
