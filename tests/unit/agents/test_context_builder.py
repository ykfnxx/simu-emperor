"""ContextBuilder 单元测试。"""

from pathlib import Path
from typing import Any

import pytest

from simu_emperor.agents.context_builder import (
    NATIONAL_ALLOWED_FIELDS,
    PROVINCE_TOP_LEVEL_FIELDS,
    SUBSYSTEM_FIELDS,
    ConfigurationError,
    ContextBuilder,
    SkillScope,
    extract_province_data,
    extract_scoped_data,
    load_rule_md,
    parse_data_scope,
    resolve_field_paths,
)
from simu_emperor.agents.file_manager import FileManager

from tests.conftest import make_national_data, make_province, make_zhili_province


# ── 字段注册表 ──


class TestFieldRegistry:
    def test_subsystem_fields_populated(self) -> None:
        assert "population" in SUBSYSTEM_FIELDS
        assert "total" in SUBSYSTEM_FIELDS["population"]
        assert "happiness" in SUBSYSTEM_FIELDS["population"]

    def test_commerce_fields(self) -> None:
        assert "merchant_households" in SUBSYSTEM_FIELDS["commerce"]
        assert "market_prosperity" in SUBSYSTEM_FIELDS["commerce"]

    def test_province_top_level(self) -> None:
        assert "granary_stock" in PROVINCE_TOP_LEVEL_FIELDS
        assert "local_treasury" in PROVINCE_TOP_LEVEL_FIELDS

    def test_national_allowed(self) -> None:
        assert "imperial_treasury" in NATIONAL_ALLOWED_FIELDS
        assert "national_tax_modifier" in NATIONAL_ALLOWED_FIELDS
        assert "tribute_rate" in NATIONAL_ALLOWED_FIELDS


# ── 字段解析 ──


class TestResolveFieldPaths:
    def test_wildcard_expansion(self) -> None:
        result = resolve_field_paths(["commerce.*"])
        assert "commerce.merchant_households" in result
        assert "commerce.market_prosperity" in result

    def test_single_field(self) -> None:
        result = resolve_field_paths(["commerce.merchant_households"])
        assert result == ["commerce.merchant_households"]

    def test_top_level_field(self) -> None:
        result = resolve_field_paths(["granary_stock"])
        assert result == ["granary_stock"]

    def test_mixed_fields(self) -> None:
        result = resolve_field_paths(["commerce.*", "granary_stock"])
        assert "commerce.merchant_households" in result
        assert "granary_stock" in result

    def test_unknown_subsystem(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown subsystem"):
            resolve_field_paths(["unknown.*"])

    def test_unknown_field(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown field"):
            resolve_field_paths(["commerce.nonexistent"])

    def test_unknown_top_level(self) -> None:
        with pytest.raises(ConfigurationError, match="Unknown top-level field"):
            resolve_field_paths(["nonexistent_field"])

    def test_dedup(self) -> None:
        result = resolve_field_paths(["commerce.*", "commerce.merchant_households"])
        count = result.count("commerce.merchant_households")
        assert count == 1


# ── inherits ──


class TestParseDataScope:
    def test_basic_inherits(self) -> None:
        raw: dict[str, Any] = {
            "display_name": "Test",
            "skills": {
                "query_data": {
                    "national": ["imperial_treasury"],
                    "provinces": "all",
                    "fields": ["commerce.*"],
                },
                "write_report": {"inherits": "query_data"},
            },
        }
        scope = parse_data_scope(raw)
        assert scope.skills["write_report"].national == ["imperial_treasury"]
        assert scope.skills["write_report"].provinces == "all"
        assert scope.skills["write_report"].fields == scope.skills["query_data"].fields

    def test_inherits_with_additional_fields(self) -> None:
        raw: dict[str, Any] = {
            "display_name": "Test",
            "skills": {
                "query_data": {
                    "provinces": ["zhili"],
                    "fields": ["commerce.*"],
                },
                "write_report": {
                    "inherits": "query_data",
                    "additional_fields": ["military.morale"],
                },
            },
        }
        scope = parse_data_scope(raw)
        wr = scope.skills["write_report"]
        assert "military.morale" in wr.fields
        assert "commerce.merchant_households" in wr.fields

    def test_multi_level_inherits_error(self) -> None:
        raw: dict[str, Any] = {
            "display_name": "Test",
            "skills": {
                "a": {"inherits": "b"},
                "b": {"inherits": "c"},
                "c": {"provinces": [], "fields": []},
            },
        }
        with pytest.raises(ConfigurationError, match="Multi-level inheritance"):
            parse_data_scope(raw)

    def test_circular_inherits_error(self) -> None:
        raw: dict[str, Any] = {
            "display_name": "Test",
            "skills": {
                "a": {"inherits": "a"},
            },
        }
        with pytest.raises(ConfigurationError, match="Circular inheritance"):
            parse_data_scope(raw)

    def test_inherits_unknown_skill(self) -> None:
        raw: dict[str, Any] = {
            "display_name": "Test",
            "skills": {
                "a": {"inherits": "nonexistent"},
            },
        }
        with pytest.raises(ConfigurationError, match="unknown skill"):
            parse_data_scope(raw)

    def test_full_minister_config(self) -> None:
        raw: dict[str, Any] = {
            "display_name": "户部尚书",
            "skills": {
                "query_data": {
                    "national": ["imperial_treasury", "national_tax_modifier", "tribute_rate"],
                    "provinces": "all",
                    "fields": [
                        "commerce.*",
                        "trade.*",
                        "taxation.*",
                        "granary_stock",
                        "local_treasury",
                    ],
                },
                "write_report": {"inherits": "query_data"},
                "execute_command": {
                    "national": ["national_tax_modifier"],
                    "provinces": "all",
                    "fields": [
                        "taxation.*",
                    ],
                },
            },
        }
        scope = parse_data_scope(raw)
        assert scope.display_name == "户部尚书"
        assert len(scope.skills) == 3
        assert scope.skills["write_report"].fields == scope.skills["query_data"].fields

    def test_full_governor_config(self) -> None:
        raw: dict[str, Any] = {
            "display_name": "直隶巡抚",
            "skills": {
                "query_data": {
                    "provinces": ["zhili"],
                    "fields": [
                        "population.*",
                        "agriculture.*",
                        "commerce.*",
                        "trade.*",
                        "military.garrison_size",
                        "military.morale",
                        "granary_stock",
                        "local_treasury",
                    ],
                },
                "write_report": {"inherits": "query_data"},
                "execute_command": {
                    "provinces": ["zhili"],
                    "fields": [
                        "agriculture.irrigation_level",
                        "taxation.commercial_tax_rate",
                        "granary_stock",
                    ],
                },
            },
        }
        scope = parse_data_scope(raw)
        assert scope.display_name == "直隶巡抚"
        qd = scope.skills["query_data"]
        assert qd.provinces == ["zhili"]
        assert "population.total" in qd.fields
        assert "military.garrison_size" in qd.fields


# ── 数据提取 ──


class TestExtractProvinceData:
    def test_extract_single_field(self) -> None:
        province = make_province()
        result = extract_province_data(province, ["granary_stock"])
        assert result == {"granary_stock": str(province.granary_stock)}

    def test_extract_subsystem_field(self) -> None:
        province = make_province()
        result = extract_province_data(province, ["commerce.merchant_households"])
        assert "commerce" in result
        assert result["commerce"]["merchant_households"] == str(
            province.commerce.merchant_households
        )

    def test_extract_crops(self) -> None:
        province = make_province()
        result = extract_province_data(province, ["agriculture.crops"])
        crops = result["agriculture"]["crops"]
        assert isinstance(crops, list)
        assert len(crops) == 1
        assert crops[0]["crop_type"] == "rice"

    def test_extract_multiple_fields(self) -> None:
        province = make_province()
        fields = ["commerce.merchant_households", "commerce.market_prosperity", "granary_stock"]
        result = extract_province_data(province, fields)
        assert "commerce" in result
        assert "granary_stock" in result
        assert len(result["commerce"]) == 2


class TestExtractScopedData:
    def test_national_only(self) -> None:
        data = make_national_data()
        scope = SkillScope(national=["imperial_treasury"], provinces=[], fields=[])
        result = extract_scoped_data(data, scope)
        assert "national" in result
        assert result["national"]["imperial_treasury"] == str(data.imperial_treasury)
        assert "provinces" not in result

    def test_provinces_all(self) -> None:
        data = make_national_data(
            provinces=[make_province("p1", "Province 1"), make_province("p2", "Province 2")]
        )
        scope = SkillScope(provinces="all", fields=["granary_stock"])
        result = extract_scoped_data(data, scope)
        assert "p1" in result["provinces"]
        assert "p2" in result["provinces"]

    def test_provinces_list(self) -> None:
        zhili = make_zhili_province()
        other = make_province("other", "Other")
        data = make_national_data(provinces=[zhili, other])
        scope = SkillScope(provinces=["zhili"], fields=["granary_stock"])
        result = extract_scoped_data(data, scope)
        assert "zhili" in result["provinces"]
        assert "other" not in result["provinces"]

    def test_empty_scope(self) -> None:
        data = make_national_data()
        scope = SkillScope()
        result = extract_scoped_data(data, scope)
        assert result == {}


# ── ContextBuilder 端到端 ──


@pytest.fixture
def setup_builder(tmp_path: Path) -> tuple[ContextBuilder, FileManager, str]:
    agent_base = tmp_path / "agent"
    template_base = tmp_path / "default_agents"
    skills_dir = tmp_path / "skills"
    agent_base.mkdir()
    template_base.mkdir()
    skills_dir.mkdir()

    fm = FileManager(agent_base, template_base, skills_dir)
    agent_id = "test_agent"

    # 创建 agent 文件
    agent_dir = agent_base / agent_id
    agent_dir.mkdir()
    (agent_dir / "soul.md").write_text("# Test Agent Soul", encoding="utf-8")
    (agent_dir / "data_scope.yaml").write_text(
        """display_name: Test Agent
skills:
  query_data:
    national: [imperial_treasury]
    provinces: all
    fields:
      - commerce.*
      - granary_stock
  write_report:
    inherits: query_data
""",
        encoding="utf-8",
    )
    fm.ensure_agent_dirs(agent_id)

    # 创建 skill 文件
    (skills_dir / "query_data.md").write_text("# Query Data Skill", encoding="utf-8")
    (skills_dir / "write_report.md").write_text("# Write Report Skill", encoding="utf-8")

    cb = ContextBuilder(fm)
    return cb, fm, agent_id


class TestContextBuilder:
    def test_load_data_scope(self, setup_builder: tuple[ContextBuilder, FileManager, str]) -> None:
        cb, _, agent_id = setup_builder
        scope = cb.load_data_scope(agent_id)
        assert scope.display_name == "Test Agent"
        assert "query_data" in scope.skills

    def test_build_context(self, setup_builder: tuple[ContextBuilder, FileManager, str]) -> None:
        cb, _, agent_id = setup_builder
        data = make_national_data()
        ctx = cb.build_context(agent_id, "query_data", data)
        assert ctx.agent_id == agent_id
        assert ctx.soul == "# Test Agent Soul"
        assert ctx.skill == "# Query Data Skill"
        assert "national" in ctx.data
        assert "provinces" in ctx.data

    def test_build_context_with_memory(
        self, setup_builder: tuple[ContextBuilder, FileManager, str]
    ) -> None:
        cb, _, agent_id = setup_builder
        data = make_national_data()
        ctx = cb.build_context(
            agent_id,
            "query_data",
            data,
            memory_summary="Summary",
            recent_memories=[(1, "Turn 1")],
        )
        assert ctx.memory_summary == "Summary"
        assert ctx.recent_memories == [(1, "Turn 1")]

    def test_build_context_unknown_skill(
        self, setup_builder: tuple[ContextBuilder, FileManager, str]
    ) -> None:
        cb, _, agent_id = setup_builder
        data = make_national_data()
        with pytest.raises(ConfigurationError, match="not found in data_scope"):
            cb.build_context(agent_id, "nonexistent_skill", data)

    def test_build_context_inherited_skill(
        self, setup_builder: tuple[ContextBuilder, FileManager, str]
    ) -> None:
        cb, _, agent_id = setup_builder
        data = make_national_data()
        ctx = cb.build_context(agent_id, "write_report", data)
        assert ctx.skill == "# Write Report Skill"
        # write_report inherits query_data, so data should be the same
        ctx_qd = cb.build_context(agent_id, "query_data", data)
        assert ctx.data == ctx_qd.data


class TestLoadRuleMd:
    """测试 RULE.md 加载功能。"""

    def test_load_rule_md_exists(self, tmp_path: Path) -> None:
        """测试 RULE.md 文件存在时正确加载。"""
        rule_content = "# Test Rule\n\n这是测试规则。"
        (tmp_path / "RULE.md").write_text(rule_content, encoding="utf-8")

        # 清除缓存
        import simu_emperor.agents.context_builder as cb_module

        cb_module._rule_cache = None

        result = load_rule_md(tmp_path)
        assert result == rule_content

    def test_load_rule_md_not_exists(self, tmp_path: Path) -> None:
        """测试 RULE.md 文件不存在时返回空字符串。"""
        import simu_emperor.agents.context_builder as cb_module

        cb_module._rule_cache = None

        result = load_rule_md(tmp_path)
        assert result == ""

    def test_load_rule_md_caching(self, tmp_path: Path) -> None:
        """测试 RULE.md 缓存机制。"""
        import simu_emperor.agents.context_builder as cb_module

        cb_module._rule_cache = None

        rule_content = "# Cached Rule"
        (tmp_path / "RULE.md").write_text(rule_content, encoding="utf-8")

        # 第一次加载
        result1 = load_rule_md(tmp_path)
        assert result1 == rule_content

        # 修改文件
        (tmp_path / "RULE.md").write_text("# Modified Rule", encoding="utf-8")

        # 第二次加载应该返回缓存值
        result2 = load_rule_md(tmp_path)
        assert result2 == rule_content  # 仍然是旧值


class TestRuleContext:
    """测试 AgentContext 中的 rule 字段。"""

    def test_context_includes_rule(
        self, setup_builder: tuple[ContextBuilder, FileManager, str]
    ) -> None:
        """测试 AgentContext 包含 rule 字段。"""
        cb, fm, agent_id = setup_builder

        # 创建 RULE.md
        rule_content = "# 官员奏折规范\n\n## 格式要求"
        (fm.template_base.parent / "RULE.md").write_text(rule_content, encoding="utf-8")

        # 清除缓存
        import simu_emperor.agents.context_builder as cb_module

        cb_module._rule_cache = None

        data = make_national_data()
        ctx = cb.build_context(agent_id, "query_data", data)

        assert ctx.rule is not None
        assert "官员奏折规范" in ctx.rule

    def test_context_rule_none_when_missing(
        self, setup_builder: tuple[ContextBuilder, FileManager, str]
    ) -> None:
        """测试 RULE.md 不存在时 rule 为 None。"""
        cb, fm, agent_id = setup_builder

        # 确保 RULE.md 不存在
        rule_path = fm.template_base.parent / "RULE.md"
        if rule_path.exists():
            rule_path.unlink()

        # 清除缓存
        import simu_emperor.agents.context_builder as cb_module

        cb_module._rule_cache = None

        data = make_national_data()
        ctx = cb.build_context(agent_id, "query_data", data)

        assert ctx.rule is None
