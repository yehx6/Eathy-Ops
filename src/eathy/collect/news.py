"""NewsAPI 客户端 — 搜索中英文健康资讯"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta

import httpx

from ..models import Article, ArticleSource

_NEWSAPI_BASE = "https://newsapi.org/v2/everything"


def _make_article_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


async def fetch_news_articles(
    api_key: str,
    queries: list[str],
    max_age_hours: int = 48,
    max_results: int = 20,
) -> tuple[Article, ...]:
    """
    通过 NewsAPI 搜索多个关键词，合并去重后返回文章。

    Args:
        api_key: NewsAPI key
        queries: 搜索关键词列表
        max_age_hours: 只保留此时间窗口内的文章
        max_results: 每个关键词最多返回条数

    Returns:
        tuple[Article, ...] 去重后按发布时间倒序
    """
    from_dt = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")

    seen_urls: set[str] = set()
    articles: list[Article] = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        for query in queries:
            params = {
                "q": query,
                "apiKey": api_key,
                "from": from_dt,
                "sortBy": "publishedAt",
                "pageSize": min(max_results, 100),
                "language": "zh" if any(ord(c) > 127 for c in query) else "en",
            }
            try:
                response = await client.get(_NEWSAPI_BASE, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                print(f"[NewsAPI] HTTP 错误 query={query!r}: {exc}")
                continue
            except Exception as exc:
                print(f"[NewsAPI] 请求失败 query={query!r}: {exc}")
                continue

            for item in data.get("articles", []):
                url = item.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                title = (item.get("title") or "").strip()
                summary = (item.get("description") or item.get("content") or "").strip()
                if len(summary) > 500:
                    summary = summary[:500] + "..."

                published_at = item.get("publishedAt", datetime.now(timezone.utc).isoformat())
                lang = "zh" if any(ord(c) > 127 for c in title) else "en"

                articles.append(Article(
                    id=_make_article_id(url),
                    title=title,
                    url=url,
                    source=ArticleSource.NEWS_API,
                    source_name=item.get("source", {}).get("name", "NewsAPI"),
                    summary=summary,
                    language=lang,
                    published_at=published_at,
                ))

    articles.sort(key=lambda a: a.published_at, reverse=True)
    return tuple(articles)
