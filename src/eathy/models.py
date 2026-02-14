"""核心数据模型 — 全部使用 frozen dataclass 保证不可变性"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ArticleSource(str, Enum):
    RSS = "rss"
    NEWS_API = "news_api"


class ContentCategory(str, Enum):
    INGREDIENT_ANALYSIS = "成分分析"
    FOOD_WARNING = "食品避雷"
    HEALTHY_ALTERNATIVE = "健康替代"
    TRENDING_TOPIC = "热点话题"
    BRAND_TEARDOWN = "品牌拆解"


class PublishStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DRY_RUN = "dry_run"


@dataclass(frozen=True)
class Article:
    """采集到的资讯条目"""
    id: str
    title: str
    url: str
    source: ArticleSource
    source_name: str
    summary: str
    language: str                    # "zh" | "en"
    published_at: str
    collected_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass(frozen=True)
class AccountProfile:
    """账号人设"""
    name: str
    domain: str
    persona: str
    target_audience: str
    tone: str
    app_name: str
    app_download_cta: str
    forbidden_topics: tuple[str, ...] = ()
    preferred_angles: tuple[str, ...] = ()
    title_max_length: int = 20
    body_max_length: int = 1000
    hashtag_count: int = 5
    call_to_action: str = ""


@dataclass(frozen=True)
class FilterResult:
    """AI 筛选结果"""
    selected_article: Article
    category: ContentCategory
    relevance_score: float
    key_points: tuple[str, ...]
    image_subject: str               # 用于图片生成的英文描述
    reasoning: str


@dataclass(frozen=True)
class GeneratedImage:
    """生成的图片"""
    path: Path
    prompt_used: str
    template_name: str


@dataclass(frozen=True)
class XhsCopywrite:
    """小红书文案"""
    title: str                       # <=20 字
    body: str                        # <=1000 字
    hashtags: tuple[str, ...]
    category: ContentCategory
    source_article_id: str


@dataclass(frozen=True)
class PublishResult:
    """发布结果"""
    status: PublishStatus
    published_at: str
    copywrite: XhsCopywrite
    images: tuple[GeneratedImage, ...]
    note_id: str = ""
    error_message: str = ""


@dataclass(frozen=True)
class PipelineResult:
    """完整管道输出"""
    articles_collected: int
    filter_result: FilterResult
    images: tuple[GeneratedImage, ...]
    copywrite: XhsCopywrite
    publish_result: PublishResult
    run_id: str
    started_at: str
    completed_at: str
