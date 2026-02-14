"""Gemini 图片生成器测试 — 适配 Gemini 原生 API"""

import base64
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from eathy.image.imagen import ImagenGenerator
from eathy.models import Article, ArticleSource, ContentCategory, FilterResult
from eathy.prompts import ImageStyle
from datetime import datetime, timezone


def make_filter_result(category=ContentCategory.INGREDIENT_ANALYSIS) -> FilterResult:
    article = Article(
        id="test-id",
        title="味精真的有害吗",
        url="https://example.com/1",
        source=ArticleSource.RSS,
        source_name="Healthline",
        summary="summary",
        language="zh",
        published_at=datetime.now(timezone.utc).isoformat(),
    )
    return FilterResult(
        selected_article=article,
        category=category,
        relevance_score=0.9,
        key_points=("要点1", "要点2"),
        image_subject="MSG monosodium glutamate food additive close-up",
        reasoning="相关性高",
    )


def _fake_png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def make_gemini_response(b64_data: str) -> MagicMock:
    """构建 Gemini 原生 API 响应"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{
                    "text": "Here is the image",
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": b64_data
                    }
                }]
            }
        }]
    }
    return mock_resp


def make_empty_gemini_response() -> MagicMock:
    """构建无图片的 Gemini 响应"""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "candidates": [{
            "content": {
                "parts": [{"text": "I cannot generate that."}]
            } # No inlineData
        }]
    }
    return mock_resp


class TestImagenGenerator:
    def make_generator(self):
        return ImagenGenerator(
            api_key="test-api-key",
            model="gemini-3-pro-image-preview",
            number_of_images=3,
        )

    def _make_style(self) -> ImageStyle:
        return ImageStyle(
            id="test-style",
            name="Test Style",
            description="Test Desc",
            prompt="Image of {subject}"
        )

    @pytest.mark.asyncio
    async def test_generate_returns_images(self, tmp_path):
        """测试解析 Gemini 原生响应的图片流程"""
        gen = self.make_generator()
        filter_result = make_filter_result()
        style = self._make_style()

        fake = _fake_png()
        b64_str = base64.b64encode(fake).decode()
        api_response = make_gemini_response(b64_str)

        async_client_mock = AsyncMock()
        async_client_mock.__aenter__ = AsyncMock(return_value=async_client_mock)
        async_client_mock.__aexit__ = AsyncMock(return_value=False)
        async_client_mock.post = AsyncMock(return_value=api_response)

        with patch("eathy.image.imagen.httpx.AsyncClient", return_value=async_client_mock):
            results = await gen.generate(filter_result, tmp_path, style)

        assert len(results) == 3
        for r in results:
            assert r.template_name == "Test Style"
            assert "MSG" in r.prompt_used
            assert r.path.exists()
            assert r.path.read_bytes() == fake
            
        # 验证请求参数
        call_args = async_client_mock.post.call_args
        assert call_args is not None
        _, kwargs = call_args
        assert kwargs["params"] == {"key": "test-api-key"}
        assert "v1beta/models/gemini-3-pro-image-preview:generateContent" in call_args[0][0]
        assert kwargs["json"]["generationConfig"]["imageConfig"]["aspectRatio"] == "3:4"

    @pytest.mark.asyncio
    async def test_raises_on_no_images(self, tmp_path):
        """所有响应都无图片数据时应抛出 RuntimeError"""
        gen = self.make_generator()
        filter_result = make_filter_result()
        style = self._make_style()

        api_response = make_empty_gemini_response()

        async_client_mock = AsyncMock()
        async_client_mock.__aenter__ = AsyncMock(return_value=async_client_mock)
        async_client_mock.__aexit__ = AsyncMock(return_value=False)
        async_client_mock.post = AsyncMock(return_value=api_response)

        with patch("eathy.image.imagen.httpx.AsyncClient", return_value=async_client_mock):
            with pytest.raises(RuntimeError, match="图片生成失败"):
                await gen.generate(filter_result, tmp_path, style)

    @pytest.mark.asyncio
    async def test_handles_partial_failures(self, tmp_path):
        """部分图片生成失败时，只要有成功的就不报错"""
        import httpx as real_httpx
        gen = ImagenGenerator(
            api_key="test-key",
            model="gemini-3-pro-image-preview",
            number_of_images=3,
        )
        filter_result = make_filter_result()
        style = self._make_style()

        fake = _fake_png()
        b64_str = base64.b64encode(fake).decode()
        good_response = make_gemini_response(b64_str)

        mock_resp_err = MagicMock()
        mock_resp_err.status_code = 500
        mock_resp_err.text = "Internal Error"
        http_err = real_httpx.HTTPStatusError(
            "500", request=MagicMock(), response=mock_resp_err
        )
        mock_resp_err.raise_for_status = MagicMock(side_effect=http_err)

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return mock_resp_err
            return good_response

        async_client_mock = AsyncMock()
        async_client_mock.__aenter__ = AsyncMock(return_value=async_client_mock)
        async_client_mock.__aexit__ = AsyncMock(return_value=False)
        async_client_mock.post = AsyncMock(side_effect=side_effect)

        with patch("eathy.image.imagen.httpx.AsyncClient", return_value=async_client_mock):
            results = await gen.generate(filter_result, tmp_path, style)

        # 3 次调用，1 次失败，应该有 2 张图片
        assert len(results) == 2
