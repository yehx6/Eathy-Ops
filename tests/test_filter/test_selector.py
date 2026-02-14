"""AI 筛选器测试"""

import json
import pytest
from unittest.mock import AsyncMock
from eathy.filter.selector import ArticleSelector, _extract_json, _format_articles
from eathy.models import Article, ArticleSource, AccountProfile, ContentCategory
from eathy.prompts import FilterPrompt
from datetime import datetime, timezone


def make_article(article_id: str = "test-id") -> Article:
    return Article(
        id=article_id,
        title="味精真的有害吗？科学解读",
        url=f"https://example.com/{article_id}",
        source=ArticleSource.RSS,
        source_name="Healthline",
        summary="味精（MSG）一直是食品添加剂争议的焦点...",
        language="zh",
        published_at=datetime.now(timezone.utc).isoformat(),
    )


def make_profile() -> AccountProfile:
    return AccountProfile(
        name="Eathy",
        domain="健康饮食 / 食品成分分析",
        persona="你吃的健康食品，真的健康吗？",
        target_audience="关注健康饮食的年轻女性",
        tone="专业但有温度",
        app_name="Eathy",
        app_download_cta="下载 Eathy App",
        forbidden_topics=("政治",),
        preferred_angles=("成分揭秘", "避雷指南"),
    )


class TestExtractJson:
    def test_plain_json(self):
        text = '{"key": "value"}'
        assert _extract_json(text) == {"key": "value"}

    def test_json_in_markdown_block(self):
        text = '```json\n{"key": "value"}\n```'
        assert _extract_json(text) == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"key": "value"} done.'
        assert _extract_json(text) == {"key": "value"}

    def test_raises_if_no_json(self):
        with pytest.raises(ValueError, match="找不到 JSON"):
            _extract_json("no json here")


class TestFormatArticles:
    def test_formats_correctly(self):
        articles = (make_article("id-1"), make_article("id-2"))
        text = _format_articles(articles)
        assert "[0]" in text
        assert "[1]" in text
        assert "味精真的有害吗" in text


class TestArticleSelector:
    def _make_mock_response(self, index: int = 0, category: str = "成分分析") -> str:
        return json.dumps({
            "selected_index": index,
            "category": category,
            "relevance_score": 0.9,
            "key_points": ["要点1", "要点2"],
            "image_subject": "food ingredient analysis close-up",
            "reasoning": "与账号人设高度相关",
        })

    def _make_prompt_config(self) -> FilterPrompt:
        return FilterPrompt(
            system_prompt="Test System Prompt",
            user_prompt="Test User Prompt: {articles_text}"
        )

    @pytest.mark.asyncio
    async def test_selects_article(self):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=self._make_mock_response(0))
        selector = ArticleSelector(mock_provider, self._make_prompt_config())
        articles = (make_article("id-1"), make_article("id-2"))
        result = await selector.select(articles, make_profile())
        assert result.selected_article == articles[0]
        assert result.relevance_score == 0.9
        assert result.category == ContentCategory.INGREDIENT_ANALYSIS

    @pytest.mark.asyncio
    async def test_maps_all_categories(self):
        categories = {
            "成分分析": ContentCategory.INGREDIENT_ANALYSIS,
            "食品避雷": ContentCategory.FOOD_WARNING,
            "健康替代": ContentCategory.HEALTHY_ALTERNATIVE,
            "热点话题": ContentCategory.TRENDING_TOPIC,
            "品牌拆解": ContentCategory.BRAND_TEARDOWN,
        }
        for cat_str, cat_enum in categories.items():
            mock_provider = AsyncMock()
            mock_provider.generate = AsyncMock(return_value=self._make_mock_response(category=cat_str))
            selector = ArticleSelector(mock_provider, self._make_prompt_config())
            result = await selector.select((make_article(),), make_profile())
            assert result.category == cat_enum

    @pytest.mark.asyncio
    async def test_raises_on_empty_articles(self):
        mock_provider = AsyncMock()
        selector = ArticleSelector(mock_provider, self._make_prompt_config())
        with pytest.raises(ValueError, match="候选文章列表为空"):
            await selector.select((), make_profile())

    @pytest.mark.asyncio
    async def test_handles_out_of_bounds_index(self):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=self._make_mock_response(index=99))
        selector = ArticleSelector(mock_provider, self._make_prompt_config())
        articles = (make_article("id-1"),)
        result = await selector.select(articles, make_profile())
        assert result.selected_article == articles[0]

    @pytest.mark.asyncio
    async def test_key_points_are_tuple(self):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=self._make_mock_response())
        selector = ArticleSelector(mock_provider, self._make_prompt_config())
        result = await selector.select((make_article(),), make_profile())
        assert isinstance(result.key_points, tuple)
