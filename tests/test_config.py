"""配置加载单元测试"""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from eathy.config import load_config, load_profile, load_prompt_templates


CONFIG_YAML = """
claude:
  api_key: ${ANTHROPIC_API_KEY}
  model: claude-haiku-4-5-20251001
minimax:
  api_key: ${MINIMAX_API_KEY}
  group_id: ${MINIMAX_GROUP_ID}
"""

PROFILE_YAML = """
account:
  name: "Eathy"
  domain: "健康饮食"
  persona: "测试人设"
  target_audience: "测试受众"
  tone: "专业温度"
  app_name: "Eathy"
  app_download_cta: "下载 Eathy"
content:
  forbidden_topics:
    - 政治
  preferred_angles:
    - 成分揭秘
  title_max_length: 20
  body_max_length: 1000
  hashtag_count: 5
style:
  call_to_action: "收藏这篇"
"""

TEMPLATES_YAML = """
templates:
  ingredient_analysis:
    description: "成分分析类图片"
    prompt: "A clean image of {subject}."
default_template: ingredient_analysis
category_template_map:
  "成分分析": ingredient_analysis
"""


class TestLoadConfig:
    def test_resolves_env_vars(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(CONFIG_YAML)

        env = {
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "MINIMAX_API_KEY": "mm-test",
            "MINIMAX_GROUP_ID": "group-123",
        }
        with patch.dict(os.environ, env):
            config = load_config(config_file)

        assert config["claude"]["api_key"] == "sk-ant-test"
        assert config["minimax"]["api_key"] == "mm-test"

    def test_raises_if_env_var_missing(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(CONFIG_YAML)

        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="环境变量未设置"):
                load_config(config_file)

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")


class TestLoadProfile:
    def test_loads_profile(self, tmp_path):
        profile_file = tmp_path / "account-profile.yaml"
        profile_file.write_text(PROFILE_YAML)

        profile = load_profile(profile_file)

        assert profile.name == "Eathy"
        assert profile.domain == "健康饮食"
        assert profile.title_max_length == 20
        assert "政治" in profile.forbidden_topics
        assert "成分揭秘" in profile.preferred_angles
        assert profile.call_to_action == "收藏这篇"

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_profile("/nonexistent/profile.yaml")


class TestLoadPromptTemplates:
    def test_loads_templates(self, tmp_path):
        templates_file = tmp_path / "prompt-templates.yaml"
        templates_file.write_text(TEMPLATES_YAML)

        templates = load_prompt_templates(templates_file)

        assert "templates" in templates
        assert "ingredient_analysis" in templates["templates"]
        assert templates["default_template"] == "ingredient_analysis"

    def test_raises_if_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_prompt_templates("/nonexistent/templates.yaml")
