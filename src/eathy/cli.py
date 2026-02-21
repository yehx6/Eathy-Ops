"""CLI 入口"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    """Eathy 小红书自动化内容发布系统"""
    pass


@cli.command()
@click.option("--dry-run", is_flag=True, help="只生成内容，不实际发布到小红书")
@click.option("--no-images", is_flag=True, help="跳过图片生成阶段")
@click.option("--config", default="config.yaml", show_default=True, help="配置文件路径")
@click.option("--profile", default="account-profile.yaml", show_default=True, help="账号人设文件路径")
@click.option("--templates", default="prompt-templates.yaml", show_default=True, help="图片提示词模板路径")
def run(dry_run: bool, no_images: bool, config: str, profile: str, templates: str):
    """执行一次完整的内容生成和发布管道"""
    from .pipeline import Pipeline

    async def _run():
        pipeline = Pipeline(
            config_path=config,
            profile_path=profile,
            templates_path=templates,
        )
        try:
            result = await pipeline.run(dry_run=dry_run, skip_images=no_images)
            return result
        except Exception as exc:
            console.print(f"[bold red]管道执行失败:[/] {exc}")
            raise SystemExit(1)

    asyncio.run(_run())


@cli.command()
@click.option("--history", default="data/history.json", show_default=True, help="历史记录文件路径")
def history(history: str):
    """查看发布历史"""
    history_file = Path(history)
    if not history_file.exists():
        console.print("[yellow]暂无发布历史[/]")
        return

    try:
        records = json.loads(history_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        console.print("[red]历史记录文件格式错误[/]")
        return

    table = Table(title=f"发布历史（共 {len(records)} 条）")
    table.add_column("序号", style="dim")
    table.add_column("发布时间")
    table.add_column("文章 ID")
    table.add_column("Run ID")

    for i, record in enumerate(reversed(records[-20:]), 1):
        table.add_row(
            str(i),
            record.get("published_at", "")[:19],
            record.get("article_id", ""),
            record.get("run_id", ""),
        )

    console.print(table)


@cli.command()
@click.option("--mcp-url", default="http://localhost:18060", show_default=True)
def status(mcp_url: str):
    """检查系统状态（MCP 服务连接 + 小红书登录状态）"""
    from .publish.xhs import XhsPublisher

    async def _check():
        publisher = XhsPublisher(mcp_server_url=mcp_url)
        console.print(f"[bold]检查 MCP 服务:[/] {mcp_url}")
        logged_in = await publisher.check_login()
        if logged_in:
            console.print("[green]小红书已登录[/]")
        else:
            console.print("[red]小红书未登录或 MCP 服务未启动[/]")
            console.print("请先启动 xiaohongshu-mcp 并完成登录")

    asyncio.run(_check())


@cli.command()
@click.option("--dry-run", is_flag=True, help="所有调度的管道都以 dry-run 模式执行")
@click.option("--config", default="config.yaml", show_default=True, help="配置文件路径")
@click.option("--profile", default="account-profile.yaml", show_default=True, help="账号人设文件路径")
@click.option("--templates", default="prompt-templates.yaml", show_default=True, help="图片提示词模板路径")
def schedule(dry_run: bool, config: str, profile: str, templates: str):
    """启动定时调度器，每天按计划自动发布（常驻进程）"""
    from .scheduler import run_scheduler

    console.print("[bold green]启动 Eathy 定时调度器...[/]")
    try:
        asyncio.run(run_scheduler(
            config_path=config,
            profile_path=profile,
            templates_path=templates,
            dry_run=dry_run,
        ))
    except KeyboardInterrupt:
        console.print("\n[yellow]调度器已停止[/]")


if __name__ == "__main__":
    cli()
