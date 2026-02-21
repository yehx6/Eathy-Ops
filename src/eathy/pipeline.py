"""管道编排 — 串联从信息采集到自动发布的完整流程"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .collect.aggregator import collect_all
from .config import load_config, load_profile, load_prompt_templates
from .copywrite.minimax import CopywriteGenerator
from .filter.selector import ArticleSelector
from .image.imagen import ImagenGenerator
from .models import PipelineResult
from .providers.minimax import MinimaxProvider
from .publish.xhs import XhsPublisher

console = Console()


def _save_history(history_file: Path, article_id: str, run_id: str) -> None:
    """追加发布记录到历史文件"""
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history: list[dict] = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            history = []
    history.append({
        "article_id": article_id,
        "run_id": run_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
    })
    history_file.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_run_output(out_dir: Path, result: PipelineResult) -> None:
    """保存本次运行的详细结果"""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 保存筛选结果
    filter_data = {
        "article": {
            "id": result.filter_result.selected_article.id,
            "title": result.filter_result.selected_article.title,
            "url": result.filter_result.selected_article.url,
            "source": result.filter_result.selected_article.source.value,
        },
        "category": result.filter_result.category.value,
        "relevance_score": result.filter_result.relevance_score,
        "key_points": list(result.filter_result.key_points),
        "image_subject": result.filter_result.image_subject,
    }
    (out_dir / "filter_result.json").write_text(
        json.dumps(filter_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 保存文案
    copywrite_data = {
        "title": result.copywrite.title,
        "body": result.copywrite.body,
        "hashtags": list(result.copywrite.hashtags),
        "category": result.copywrite.category.value,
    }
    (out_dir / "copywrite.json").write_text(
        json.dumps(copywrite_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 保存发布结果
    publish_data = {
        "status": result.publish_result.status.value,
        "note_id": result.publish_result.note_id,
        "published_at": result.publish_result.published_at,
        "error_message": result.publish_result.error_message,
    }
    (out_dir / "publish_result.json").write_text(
        json.dumps(publish_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class Pipeline:
    def __init__(
        self,
        config_path: str | Path = "config.yaml",
        profile_path: str | Path = "account-profile.yaml",
        templates_path: str | Path = "prompt-templates.yaml",
    ) -> None:
        self._config_path = Path(config_path)
        self._profile_path = Path(profile_path)
        self._templates_path = Path(templates_path)

    async def run(self, dry_run: bool = False, skip_images: bool = False) -> PipelineResult:
        """执行完整管道：采集 → 筛选 → 生图 → 文案 → 发布"""
        started_at = datetime.now(timezone.utc).isoformat()
        run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # 加载配置
        config = load_config(self._config_path)
        profile = load_profile(self._profile_path)
        
        # 共享 AI Provider
        minimax_cfg = config["minimax"]
        api_type = minimax_cfg.get("api_type", "anthropic")
        if api_type == "openai":
            from .providers import OpenAICompatProvider
            ai_provider = OpenAICompatProvider(
                api_key=minimax_cfg["api_key"],
                model=minimax_cfg.get("model", "deepseek-chat"),
                base_url=minimax_cfg.get("base_url", "https://api.deepseek.com"),
            )
        else:
            ai_provider = MinimaxProvider(
                api_key=minimax_cfg["api_key"],
                model=minimax_cfg.get("model", "MiniMax-M2.5"),
                base_url=minimax_cfg.get("base_url", "https://api.minimax.io/anthropic"),
            )
        
        # 初始化样式管理器
        from .prompts import StyleManager
        style_manager = StyleManager(config.get("prompts", {}), ai_provider)

        output_cfg = config.get("output", {})
        output_dir = Path(output_cfg.get("dir", "./output")) / run_id
        history_file = Path(output_cfg.get("history_file", "./data/history.json"))
        images_dir = output_dir / "images"

        console.print(Panel(f"[bold green]Eathy Ops 内容发布管道[/] run_id={run_id}", expand=False))

        # 阶段 1: 信息采集
        console.print("[bold]1/6[/] 信息采集中...")
        articles = await collect_all(config, history_file=history_file)
        if not articles:
            raise RuntimeError("未采集到任何候选文章，请检查 RSS feeds 和 NewsAPI 配置")
        console.print(f"    采集到 {len(articles)} 条候选文章")

        # 阶段 2: AI 筛选
        console.print("[bold]2/6[/] AI 筛选最佳资讯...")
        selector = ArticleSelector(ai_provider, style_manager.get_filter_prompt())
        filter_result = await selector.select(articles, profile)
        console.print(f"    选中: [{filter_result.category.value}] {filter_result.selected_article.title}")
        console.print(f"    相关性: {filter_result.relevance_score:.2f}")
        
        # 阶段 3: AI 风格决策
        console.print("[bold]3/6[/] AI 决策内容风格...")
        copy_style, img_style = await style_manager.select_best_styles(filter_result.selected_article)
        console.print(f"    文案风格: [cyan]{copy_style.name}[/] ({copy_style.description})")
        console.print(f"    配图风格: [cyan]{img_style.name}[/] ({img_style.description})")

        # 阶段 4: 图片生成
        if skip_images:
            console.print("[bold]4/6[/] 跳过图片生成（--no-images）")
            images: list[Path] = []
        else:
            console.print("[bold]4/6[/] 生成小红书配图...")
            imagen_cfg = config["imagen"]
            imagen_api_type = imagen_cfg.get("api_type", "gemini")
            if imagen_api_type == "doubao":
                from .image.doubao import DoubaoImageGenerator
                imagen = DoubaoImageGenerator(
                    api_key=imagen_cfg["api_key"],
                    model=imagen_cfg.get("model", "doubao-seedream-4-5-251128"),
                    number_of_images=imagen_cfg.get("number_of_images", 3),
                    image_size=imagen_cfg.get("image_size", "2048x2720"),
                    base_url=imagen_cfg.get("base_url", "https://ark.cn-beijing.volces.com/api/v3"),
                )
            else:
                imagen = ImagenGenerator(
                    api_key=imagen_cfg["api_key"],
                    model=imagen_cfg.get("model", "gemini-3-pro-image-preview"),
                    number_of_images=imagen_cfg.get("number_of_images", 3),
                    image_size=imagen_cfg.get("image_size", "3:4"),
                    base_url=imagen_cfg.get("base_url", "https://new.12ai.org"),
                )
            images = await imagen.generate(filter_result, images_dir, img_style)
            console.print(f"    生成 {len(images)} 张图片")

        # 阶段 5: 文案生成
        console.print("[bold]5/6[/] 生成小红书文案...")
        copywrite_gen = CopywriteGenerator(ai_provider)
        copywrite = await copywrite_gen.generate(filter_result, profile, copy_style)
        console.print(f"    标题: {copywrite.title}")
        console.print(f"    标签: {', '.join(copywrite.hashtags)}")

        # 阶段 5: 自动发布
        console.print("[bold]5/5[/] 发布到小红书...")
        publish_cfg = config.get("publish", {})
        publisher = XhsPublisher(
            mcp_server_url=publish_cfg.get("mcp_server_url", "http://localhost:18060"),
            dry_run=dry_run or publish_cfg.get("dry_run", False),
            images_host_dir=publish_cfg.get("images_host_dir", ""),
            images_container_dir=publish_cfg.get("images_container_dir", "/app/images"),
        )
        publish_result = await publisher.publish(copywrite, images)
        console.print(f"    状态: [bold]{publish_result.status.value}[/]")
        if publish_result.error_message:
            console.print(f"    错误: [red]{publish_result.error_message}[/]")

        completed_at = datetime.now(timezone.utc).isoformat()

        result = PipelineResult(
            articles_collected=len(articles),
            filter_result=filter_result,
            images=images,
            copywrite=copywrite,
            publish_result=publish_result,
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
        )

        # 保存结果
        _save_run_output(output_dir, result)
        if publish_result.status.value == "published":
            _save_history(history_file, filter_result.selected_article.id, run_id)
            console.print(f"[green]发布成功！[/] 笔记 ID: {publish_result.note_id}")
        elif publish_result.status.value == "dry_run":
            console.print("[yellow]Dry run 模式，未实际发布[/]")

        console.print(f"[dim]输出目录: {output_dir}[/]")
        return result
