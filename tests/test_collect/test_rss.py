"""RSS 解析器测试"""

import pytest
from unittest.mock import patch, MagicMock
from eathy.collect.rss import fetch_rss_articles, _is_recent, _make_article_id
from eathy.models import ArticleSource


class TestIsRecent:
    def test_recent_article(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        assert _is_recent(now, max_age_hours=48) is True

    def test_old_article(self):
        assert _is_recent("2020-01-01T00:00:00+00:00", max_age_hours=48) is False

    def test_invalid_date_returns_true(self):
        assert _is_recent("invalid-date", max_age_hours=48) is True


class TestMakeArticleId:
    def test_consistent_id(self):
        url = "https://example.com/article/1"
        assert _make_article_id(url) == _make_article_id(url)

    def test_different_urls_different_ids(self):
        assert _make_article_id("https://a.com") != _make_article_id("https://b.com")

    def test_id_length(self):
        assert len(_make_article_id("https://example.com")) == 12


class TestFetchRssArticles:
    def _make_mock_entry(self, title="Test Article", link="https://example.com/1", summary="Summary text"):
        entry = MagicMock()
        entry.title = title
        entry.link = link
        entry.summary = summary
        entry.description = ""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        entry.published_parsed = now.timetuple()[:6]
        entry.updated_parsed = None
        return entry

    def test_returns_tuple(self):
        mock_feed = MagicMock()
        mock_feed.entries = []
        with patch("feedparser.parse", return_value=mock_feed):
            result = fetch_rss_articles([{"name": "Test", "url": "https://example.com", "lang": "en"}])
        assert isinstance(result, tuple)

    def test_parses_entries(self):
        entry = self._make_mock_entry()
        mock_feed = MagicMock()
        mock_feed.entries = [entry]
        with patch("feedparser.parse", return_value=mock_feed):
            result = fetch_rss_articles([{"name": "Test", "url": "https://example.com", "lang": "en"}])
        assert len(result) == 1
        assert result[0].title == "Test Article"
        assert result[0].source == ArticleSource.RSS
        assert result[0].language == "en"

    def test_skips_entry_without_url(self):
        entry = MagicMock()
        entry.link = ""
        mock_feed = MagicMock()
        mock_feed.entries = [entry]
        with patch("feedparser.parse", return_value=mock_feed):
            result = fetch_rss_articles([{"name": "Test", "url": "https://example.com", "lang": "en"}])
        assert len(result) == 0

    def test_handles_parse_exception(self):
        with patch("feedparser.parse", side_effect=Exception("network error")):
            result = fetch_rss_articles([{"name": "Test", "url": "https://example.com", "lang": "en"}])
        assert result == ()

    def test_truncates_long_summary(self):
        long_summary = "x" * 600
        entry = self._make_mock_entry(summary=long_summary)
        mock_feed = MagicMock()
        mock_feed.entries = [entry]
        with patch("feedparser.parse", return_value=mock_feed):
            result = fetch_rss_articles([{"name": "Test", "url": "https://example.com", "lang": "en"}])
        assert len(result[0].summary) <= 503  # 500 + "..."

    def test_empty_feeds_returns_empty(self):
        result = fetch_rss_articles([])
        assert result == ()
