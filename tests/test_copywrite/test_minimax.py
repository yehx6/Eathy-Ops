"""文案生成器测试"""

import json
import pytest
from unittest.mock import AsyncMock
from eathy.copywrite.minimax import CopywriteGenerator, _extract_json
from eathy.models import Article, ArticleSource, AccountProfile, ContentCategory, FilterResult
from eathy.prompts import CopywriteStyle
from datetime import datetime, timezone


def make_filter_result() -> FilterResult:
    article = Article(
        id="test-id",
        title="味精真的有害吗？科学解读",
        url="https://example.com/1",
        source=ArticleSource.RSS,
        source_name="Healthline",
        summary="关于味精的争议",
        language="zh",
        published_at=datetime.now(timezone.utc).isoformat(),
    )
    return FilterResult(
        selected_article=article,
        category=ContentCategory.INGREDIENT_ANALYSIS,
        relevance_score=0.9,
        key_points=("味精是谷氨酸钠", "适量食用安全", "中餐馆综合症是误解"),
        image_subject="MSG food additive close-up",
        reasoning="高度相关",
    )


def make_profile() -> AccountProfile:
    return AccountProfile(
        name="Eathy",
        domain="健康饮食 / 食品成分分析",
        persona="你吃的健康食品，真的健康吗？",
        target_audience="关注健康饮食的年轻女性",
        tone="专业但有温度",
        app_name="Eathy",
        app_download_cta="下载 Eathy App，扫一扫配料表就知道",
        call_to_action="收藏这篇避雷帖！",
        title_max_length=20,
        body_max_length=1000,
        hashtag_count=5,
    )


def make_mock_response(title="味精究竟有没有害", body="正文内容" * 50, hashtags=None) -> str:
    return json.dumps({
        "title": title,
        "body": body,
        "hashtags": hashtags or ["健康饮食", "成分分析", "食品安全", "减脂", "配料表"],
    })


class TestExtractJson:
    def test_plain_json(self):
        text = '{"title": "test", "body": "body", "hashtags": []}'
        result = _extract_json(text)
        assert result["title"] == "test"
        
    def test_markdown_wrapped(self):
        text = '```json\n{"title": "test"}\n```'
        result = _extract_json(text)
        assert result["title"] == "test"


class TestCopywriteGenerator:
    def _make_style(self) -> CopywriteStyle:
        return CopywriteStyle(
            id="test",
            name="Test",
            description="Test",
            system_prompt="System",
            user_prompt="User {article_title}"
        )

    @pytest.mark.asyncio
    async def test_generates_copywrite(self):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=make_mock_response())
        gen = CopywriteGenerator(mock_provider)
        result = await gen.generate(make_filter_result(), make_profile(), self._make_style())
        assert result.title == "味精究竟有没有害"
        assert len(result.hashtags) == 5
        assert result.category == ContentCategory.INGREDIENT_ANALYSIS
        assert result.source_article_id == "test-id"

    @pytest.mark.asyncio
    async def test_truncates_long_title(self):
        long_title = "这是一个超过二十字的标题内容测试用例超长了"
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=make_mock_response(title=long_title))
        gen = CopywriteGenerator(mock_provider)
        result = await gen.generate(make_filter_result(), make_profile(), self._make_style())
        assert len(result.title) <= 20

    @pytest.mark.asyncio
    async def test_truncates_long_body(self):
        long_body = "正文" * 600  # 1200 字
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=make_mock_response(body=long_body))
        gen = CopywriteGenerator(mock_provider)
        result = await gen.generate(make_filter_result(), make_profile(), self._make_style())
        assert len(result.body) <= 1000

    @pytest.mark.asyncio
    async def test_hashtags_are_tuple(self):
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=make_mock_response())
        gen = CopywriteGenerator(mock_provider)
        result = await gen.generate(make_filter_result(), make_profile(), self._make_style())
        assert isinstance(result.hashtags, tuple)

    @pytest.mark.asyncio
    async def test_limits_hashtag_count(self):
        tags = ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7"]
        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=make_mock_response(hashtags=tags))
        gen = CopywriteGenerator(mock_provider)
        result = await gen.generate(make_filter_result(), make_profile(), self._make_style())
        assert len(result.hashtags) <= 5
