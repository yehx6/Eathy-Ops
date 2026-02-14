"""配置加载 — 支持 ${ENV_VAR} 语法替换环境变量"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import AccountProfile

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: object) -> object:
    """递归替换配置中的 ${ENV_VAR} 占位符"""
    if isinstance(value, str):
        def replace(m: re.Match) -> str:
            var = m.group(1)
            result = os.environ.get(var, "")
            if not result:
                raise ValueError(f"环境变量未设置: {var}")
            return result
        return _ENV_VAR_RE.sub(replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def load_config(config_path: str | Path = "config.yaml") -> dict:
    """加载并返回配置字典（环境变量已替换）"""
    load_dotenv()
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _resolve_env_vars(raw)


def load_profile(profile_path: str | Path = "account-profile.yaml") -> AccountProfile:
    """加载账号人设配置"""
    path = Path(profile_path)
    if not path.exists():
        raise FileNotFoundError(f"人设文件不存在: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    account = data.get("account", {})
    content = data.get("content", {})
    style = data.get("style", {})
    return AccountProfile(
        name=account.get("name", ""),
        domain=account.get("domain", ""),
        persona=account.get("persona", ""),
        target_audience=account.get("target_audience", ""),
        tone=account.get("tone", ""),
        app_name=account.get("app_name", ""),
        app_download_cta=account.get("app_download_cta", ""),
        forbidden_topics=tuple(content.get("forbidden_topics", [])),
        preferred_angles=tuple(content.get("preferred_angles", [])),
        title_max_length=content.get("title_max_length", 20),
        body_max_length=content.get("body_max_length", 1000),
        hashtag_count=content.get("hashtag_count", 5),
        call_to_action=style.get("call_to_action", ""),
    )


def load_prompt_templates(templates_path: str | Path = "prompt-templates.yaml") -> dict:
    """加载图片提示词模板"""
    path = Path(templates_path)
    if not path.exists():
        raise FileNotFoundError(f"提示词模板文件不存在: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))
