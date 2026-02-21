"""小红书发布器 — 通过 xiaohongshu-mcp Streamable HTTP API 发布笔记"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..models import GeneratedImage, PublishResult, PublishStatus, XhsCopywrite

_MCP_PROTOCOL_VERSION = "2024-11-05"


class XhsPublisher:
    """
    通过 xiaohongshu-mcp 的 Streamable HTTP API 发布小红书笔记。

    xiaohongshu-mcp 使用 MCP Streamable HTTP 协议，每个会话需要：
      1. initialize (获取 Mcp-Session-Id)
      2. notifications/initialized
      3. tools/call (带 Mcp-Session-Id header)

    默认监听 http://localhost:18060
    """

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:18060",
        dry_run: bool = False,
        images_host_dir: str = "",
        images_container_dir: str = "/app/images",
    ) -> None:
        # 兼容 config 中 URL 带不带 /mcp 的情况
        base = mcp_server_url.rstrip("/")
        if base.endswith("/mcp"):
            base = base[:-4]
        self._base_url = base
        self._dry_run = dry_run
        self._images_host_dir = Path(images_host_dir) if images_host_dir else None
        self._images_container_dir = images_container_dir

    async def _create_session(self, client: httpx.AsyncClient) -> str:
        """初始化 MCP 会话，返回 session ID"""
        url = f"{self._base_url}/mcp"

        # Step 1: initialize
        init_resp = await client.post(url, json={
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {
                "protocolVersion": _MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "eathy-xhs", "version": "0.1.0"},
            },
            "id": 1,
        })
        init_resp.raise_for_status()
        session_id = init_resp.headers.get("mcp-session-id", "")
        if not session_id:
            raise RuntimeError("MCP 服务未返回 Mcp-Session-Id")

        # Step 2: notifications/initialized
        await client.post(
            url,
            headers={"Mcp-Session-Id": session_id},
            json={"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )

        return session_id

    async def _call_mcp_tool(self, tool_name: str, arguments: dict) -> dict:
        """通过 MCP Streamable HTTP 协议调用工具（完整会话流程）"""
        url = f"{self._base_url}/mcp"

        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
            session_id = await self._create_session(client)

            # Step 3: tools/call — 发布操作可能需要较长时间（浏览器自动化上传图片）
            response = await client.post(
                url,
                headers={"Mcp-Session-Id": session_id},
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                    "id": 2,
                },
                timeout=600.0,
            )
            response.raise_for_status()
            result = response.json()

        if "error" in result:
            raise RuntimeError(f"MCP 错误: {result['error']}")
        return result.get("result", {})

    async def check_login(self) -> bool:
        """检查小红书登录状态"""
        try:
            result = await self._call_mcp_tool("check_login_status", {})
            content = result.get("content", [{}])
            text = content[0].get("text", "") if content else ""
            return "已登录" in text or "logged in" in text.lower()
        except Exception:
            return False

    async def publish(
        self,
        copywrite: XhsCopywrite,
        images: tuple[GeneratedImage, ...],
    ) -> PublishResult:
        """
        发布小红书图文笔记。

        Args:
            copywrite: 文案（标题、正文、标签）
            images: 生成的图片列表

        Returns:
            PublishResult
        """
        published_at = datetime.now(timezone.utc).isoformat()

        if self._dry_run:
            print(f"[DRY RUN] 标题: {copywrite.title}")
            print(f"[DRY RUN] 正文:\n{copywrite.body}")
            print(f"[DRY RUN] 标签: {', '.join(copywrite.hashtags)}")
            print(f"[DRY RUN] 图片数: {len(images)}")
            return PublishResult(
                status=PublishStatus.DRY_RUN,
                published_at=published_at,
                copywrite=copywrite,
                images=images,
            )

        # 检查登录状态
        if not await self.check_login():
            return PublishResult(
                status=PublishStatus.FAILED,
                published_at=published_at,
                copywrite=copywrite,
                images=images,
                error_message="小红书未登录，请先运行 xiaohongshu-mcp 并完成登录",
            )

        # 构建图片路径 — MCP 在 Docker 中时需复制到挂载目录并使用容器内路径
        if self._images_host_dir:
            self._images_host_dir.mkdir(parents=True, exist_ok=True)
            image_paths = []
            for img in images:
                dest = self._images_host_dir / img.path.name
                shutil.copy2(img.path, dest)
                image_paths.append(f"{self._images_container_dir}/{img.path.name}")
        else:
            image_paths = [str(img.path.resolve()) for img in images]
        tags = list(copywrite.hashtags)

        try:
            result = await self._call_mcp_tool("publish_content", {
                "title": copywrite.title,
                "content": copywrite.body,
                "images": image_paths,
                "tags": tags,
            })
            content = result.get("content", [{}])
            text = content[0].get("text", "") if content else ""

            return PublishResult(
                status=PublishStatus.PUBLISHED,
                published_at=published_at,
                copywrite=copywrite,
                images=images,
                note_id=text.strip(),
            )

        except Exception as exc:
            return PublishResult(
                status=PublishStatus.FAILED,
                published_at=published_at,
                copywrite=copywrite,
                images=images,
                error_message=str(exc) or type(exc).__name__,
            )
