"""聚合器测试"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from eathy.collect.aggregator import collect_all, _load_published_ids
from eathy.models import Article, ArticleSource
from datetime import datetime, timezone


def make_article(article_id: str, url: str = None, published_at: str = None) -> Article:
    return Article(
        id=article_id,
        title=f"Article {article_id}",
        url=url or f"https://example.com/{article_id}",
        source=ArticleSource.RSS,
        source_name="Test",
        summary="summary",
        language="en",
        published_at=published_at or datetime.now(timezone.utc).isoformat(),
    )


class TestLoadPublishedIds:
    def test_returns_empty_if_no_file(self, tmp_path):
        result = _load_published_ids(tmp_path / "nonexistent.json")
        assert result == set()

    def test_loads_ids(self, tmp_path):
        history = [{"article_id": "abc123"}, {"article_id": "def456"}]
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps(history))
        result = _load_published_ids(history_file)
        assert result == {"abc123", "def456"}

    def test_handles_malformed_json(self, tmp_path):
        history_file = tmp_path / "history.json"
        history_file.write_text("not valid json")
        result = _load_published_ids(history_file)
        assert result == set()


class TestCollectAll:
    def _make_config(self):
        return {
            "collect": {
                "rss_feeds": [{"name": "Test", "url": "https://example.com/rss", "lang": "en"}],
                "news_api": {"api_key": "", "queries": [], "max_results": 5},
                "max_age_hours": 48,
            },
            "filter": {"max_candidates": 10},
        }

    @pytest.mark.asyncio
    async def test_deduplicates_articles(self):
        article = make_article("dup-id", url="https://example.com/dup")
        with patch("eathy.collect.aggregator.fetch_rss_articles", return_value=(article, article)):
            result = await collect_all(self._make_config())
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_filters_published_articles(self, tmp_path):
        article = make_article("published-id")
        history_file = tmp_path / "history.json"
        history_file.write_text(json.dumps([{"article_id": "published-id"}]))
        with patch("eathy.collect.aggregator.fetch_rss_articles", return_value=(article,)):
            result = await collect_all(self._make_config(), history_file=history_file)
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_respects_max_candidates(self):
        articles = tuple(make_article(f"id-{i}") for i in range(20))
        config = self._make_config()
        config["filter"]["max_candidates"] = 5
        with patch("eathy.collect.aggregator.fetch_rss_articles", return_value=articles):
            result = await collect_all(config)
        assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_returns_tuple(self):
        with patch("eathy.collect.aggregator.fetch_rss_articles", return_value=()):
            result = await collect_all(self._make_config())
        assert isinstance(result, tuple)
