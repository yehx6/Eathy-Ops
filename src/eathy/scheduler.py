"""调度器 — 每天定时执行发布管道，支持随机抖动"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import load_config

logger = logging.getLogger("eathy.scheduler")

# ─── 默认配置 ────────────────────────────────────────────
DEFAULT_TIMES = [time(8, 0), time(12, 0), time(20, 0)]
DEFAULT_JITTER_MINUTES = 30
DEFAULT_TZ = "Asia/Shanghai"


def _parse_times(raw: list[str]) -> list[time]:
    """解析 '08:00' 格式时间列表"""
    result = []
    for s in raw:
        h, m = s.strip().split(":")
        result.append(time(int(h), int(m)))
    return sorted(result)


def _next_run(
    now: datetime,
    schedule_times: list[time],
    jitter_minutes: int,
    tz: ZoneInfo,
) -> datetime:
    """
    计算下一次执行时间。

    从 schedule_times 中找到今天或明天最近的执行时间，
    然后加上 [-jitter, +jitter] 分钟的随机偏移。
    如果计算出的时间已过，跳到下一个 slot。
    """
    local_now = now.astimezone(tz)
    today = local_now.date()

    # 收集今天剩余 + 明天全部的候选时间
    candidates: list[datetime] = []
    for base_time in schedule_times:
        for offset_days in (0, 1):
            dt = datetime.combine(today + timedelta(days=offset_days), base_time, tzinfo=tz)
            if dt > local_now:
                candidates.append(dt)

    if not candidates:
        # 所有时间都过了（理论上不会到这里），用明天第一个
        dt = datetime.combine(today + timedelta(days=1), schedule_times[0], tzinfo=tz)
        candidates.append(dt)

    base = candidates[0]

    # 随机抖动
    jitter = random.randint(-jitter_minutes, jitter_minutes)
    return base + timedelta(minutes=jitter)


def _setup_logging(log_dir: Path) -> None:
    """配置日志输出到文件和控制台"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "scheduler.log"

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger("eathy")
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


async def run_scheduler(
    config_path: str = "config.yaml",
    profile_path: str = "account-profile.yaml",
    templates_path: str = "prompt-templates.yaml",
    dry_run: bool = False,
) -> None:
    """
    调度器主循环 — 永不退出。

    每到计划时间点，执行一次完整的管道。
    单次执行失败不影响后续调度。
    """
    from .pipeline import Pipeline

    config = load_config(config_path)
    schedule_cfg = config.get("schedule", {})
    output_cfg = config.get("output", {})

    raw_times = schedule_cfg.get("times", ["08:00", "12:00", "20:00"])
    jitter_minutes = int(schedule_cfg.get("jitter_minutes", DEFAULT_JITTER_MINUTES))
    tz_name = schedule_cfg.get("timezone", DEFAULT_TZ)
    tz = ZoneInfo(tz_name)
    log_dir = Path(output_cfg.get("log_dir", "./data/logs"))

    _setup_logging(log_dir)

    schedule_times = _parse_times(raw_times)
    times_display = ", ".join(t.strftime("%H:%M") for t in schedule_times)

    logger.info("═" * 50)
    logger.info("Eathy Ops 调度器启动")
    logger.info(f"  计划时间: {times_display} ({tz_name})")
    logger.info(f"  随机抖动: ±{jitter_minutes} 分钟")
    logger.info(f"  Dry-run:  {dry_run}")
    logger.info("═" * 50)

    run_count = 0

    while True:
        now = datetime.now(tz=timezone.utc)
        next_time = _next_run(now, schedule_times, jitter_minutes, tz)
        wait_seconds = max(0, (next_time.astimezone(timezone.utc) - now).total_seconds())
        local_next = next_time.strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"⏰ 下次执行: {local_next} ({tz_name})，等待 {wait_seconds/60:.0f} 分钟")

        await asyncio.sleep(wait_seconds)

        run_count += 1
        logger.info(f"🚀 开始第 {run_count} 次执行...")

        try:
            pipeline = Pipeline(
                config_path=config_path,
                profile_path=profile_path,
                templates_path=templates_path,
            )
            result = await pipeline.run(dry_run=dry_run)
            status = result.publish_result.status.value
            logger.info(f"✅ 第 {run_count} 次执行完成，状态: {status}")
        except Exception as exc:
            logger.error(f"❌ 第 {run_count} 次执行失败: {exc}", exc_info=True)

        # 执行后短暂等待，避免同一个时间窗口重复触发
        await asyncio.sleep(60)
