"""发布器测试"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from eathy.publish.xhs import XhsPublisher
from eathy.models import (
    ContentCategory, GeneratedImage, PublishStatus, XhsCopywrite,
)


def make_copywrite() -> XhsCopywrite:
    return XhsCopywrite(
        title="味精真的有害吗",
        body="正文内容测试" * 10,
        hashtags=("健康饮食", "成分分析", "食品安全", "减脂", "配料表"),
        category=ContentCategory.INGREDIENT_ANALYSIS,
        source_article_id="test-id",
    )


def make_images() -> tuple[GeneratedImage, ...]:
    return (
        GeneratedImage(path=Path("/tmp/img_1.png"), prompt_used="prompt", template_name="ingredient_analysis"),
        GeneratedImage(path=Path("/tmp/img_2.png"), prompt_used="prompt", template_name="ingredient_analysis"),
    )


class TestXhsPublisher:
    @pytest.mark.asyncio
    async def test_dry_run_returns_dry_run_status(self):
        publisher = XhsPublisher(dry_run=True)
        result = await publisher.publish(make_copywrite(), make_images())
        assert result.status == PublishStatus.DRY_RUN
        assert result.error_message == ""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_mcp(self):
        publisher = XhsPublisher(dry_run=True)
        with patch.object(publisher, "_call_mcp_tool") as mock_call:
            await publisher.publish(make_copywrite(), make_images())
            mock_call.assert_not_called()

    @pytest.mark.asyncio
    async def test_fails_if_not_logged_in(self):
        publisher = XhsPublisher(dry_run=False)
        with patch.object(publisher, "check_login", return_value=False):
            result = await publisher.publish(make_copywrite(), make_images())
        assert result.status == PublishStatus.FAILED
        assert "未登录" in result.error_message

    @pytest.mark.asyncio
    async def test_publishes_successfully(self):
        publisher = XhsPublisher(dry_run=False)
        mock_result = {"content": [{"text": "note_12345"}]}
        with patch.object(publisher, "check_login", return_value=True):
            with patch.object(publisher, "_call_mcp_tool", return_value=mock_result):
                result = await publisher.publish(make_copywrite(), make_images())
        assert result.status == PublishStatus.PUBLISHED
        assert result.note_id == "note_12345"

    @pytest.mark.asyncio
    async def test_returns_failed_on_mcp_error(self):
        publisher = XhsPublisher(dry_run=False)
        with patch.object(publisher, "check_login", return_value=True):
            with patch.object(publisher, "_call_mcp_tool", side_effect=Exception("network error")):
                result = await publisher.publish(make_copywrite(), make_images())
        assert result.status == PublishStatus.FAILED
        assert "network error" in result.error_message

    @pytest.mark.asyncio
    async def test_check_login_returns_false_on_error(self):
        publisher = XhsPublisher()
        with patch.object(publisher, "_call_mcp_tool", side_effect=Exception("connection refused")):
            result = await publisher.check_login()
        assert result is False
