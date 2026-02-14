"""数据模型单元测试"""

import pytest
from pathlib import Path
from eathy.models import (
    Article, ArticleSource, AccountProfile, FilterResult,
    ContentCategory, GeneratedImage, XhsCopywrite, PublishResult,
    PublishStatus, PipelineResult,
)


def make_article(**kwargs) -> Article:
    defaults = dict(
        id="test-id",
        title="测试标题",
        url="https://example.com/article",
        source=ArticleSource.RSS,
        source_name="Test RSS",
        summary="这是一篇测试文章摘要",
        language="zh",
        published_at="2026-02-14T08:00:00",
    )
    defaults.update(kwargs)
    return Article(**defaults)


def make_profile(**kwargs) -> AccountProfile:
    defaults = dict(
        name="Eathy",
        domain="健康饮食 / 食品成分分析",
        persona="你吃的健康食品，真的健康吗？",
        target_audience="关注健康饮食的年轻女性",
        tone="专业但有温度",
        app_name="Eathy",
        app_download_cta="下载 Eathy App",
    )
    defaults.update(kwargs)
    return AccountProfile(**defaults)


class TestArticle:
    def test_create(self):
        article = make_article()
        assert article.id == "test-id"
        assert article.source == ArticleSource.RSS
        assert article.language == "zh"

    def test_immutable(self):
        article = make_article()
        with pytest.raises(Exception):
            article.title = "修改标题"  # type: ignore

    def test_collected_at_auto_set(self):
        article = make_article()
        assert article.collected_at != ""


class TestAccountProfile:
    def test_create(self):
        profile = make_profile()
        assert profile.name == "Eathy"
        assert profile.title_max_length == 20
        assert profile.body_max_length == 1000

    def test_immutable(self):
        profile = make_profile()
        with pytest.raises(Exception):
            profile.name = "Other"  # type: ignore

    def test_tuple_fields_default_empty(self):
        profile = make_profile()
        assert profile.forbidden_topics == ()
        assert profile.preferred_angles == ()

    def test_tuple_fields_with_values(self):
        profile = make_profile(
            forbidden_topics=("政治", "医疗建议"),
            preferred_angles=("成分揭秘", "避雷指南"),
        )
        assert "政治" in profile.forbidden_topics
        assert "成分揭秘" in profile.preferred_angles


class TestFilterResult:
    def test_create(self):
        article = make_article()
        result = FilterResult(
            selected_article=article,
            category=ContentCategory.INGREDIENT_ANALYSIS,
            relevance_score=0.9,
            key_points=("成分X有害", "建议避免"),
            image_subject="food ingredient analysis close-up",
            reasoning="与账号人设高度相关",
        )
        assert result.relevance_score == 0.9
        assert len(result.key_points) == 2
        assert result.category == ContentCategory.INGREDIENT_ANALYSIS

    def test_immutable(self):
        article = make_article()
        result = FilterResult(
            selected_article=article,
            category=ContentCategory.FOOD_WARNING,
            relevance_score=0.8,
            key_points=("要点",),
            image_subject="subject",
            reasoning="reason",
        )
        with pytest.raises(Exception):
            result.relevance_score = 0.5  # type: ignore

    def test_brand_teardown_category(self):
        article = make_article()
        result = FilterResult(
            selected_article=article,
            category=ContentCategory.BRAND_TEARDOWN,
            relevance_score=0.95,
            key_points=("热量低", "性价比高"),
            image_subject="McDonald's burger flat lay",
            reasoning="品牌拆解类内容互动率最高",
        )
        assert result.category == ContentCategory.BRAND_TEARDOWN
        assert result.relevance_score == 0.95


class TestXhsCopywrite:
    def test_create(self):
        cw = XhsCopywrite(
            title="这10种零食含有害添加剂",
            body="正文内容" * 10,
            hashtags=("健康饮食", "成分分析", "避雷"),
            category=ContentCategory.FOOD_WARNING,
            source_article_id="test-id",
        )
        assert len(cw.title) <= 20
        assert isinstance(cw.hashtags, tuple)

    def test_immutable(self):
        cw = XhsCopywrite(
            title="标题",
            body="正文",
            hashtags=("标签",),
            category=ContentCategory.INGREDIENT_ANALYSIS,
            source_article_id="id",
        )
        with pytest.raises(Exception):
            cw.title = "新标题"  # type: ignore


class TestGeneratedImage:
    def test_create(self):
        img = GeneratedImage(
            path=Path("/tmp/test.png"),
            prompt_used="A clean food image",
            template_name="ingredient_analysis",
        )
        assert img.path == Path("/tmp/test.png")
        assert img.template_name == "ingredient_analysis"
