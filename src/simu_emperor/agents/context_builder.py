"""组装 LLM 调用上下文（含 data_scope 解析和数据提取）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from simu_emperor.agents.file_manager import FileManager
from simu_emperor.engine.models.base_data import (
    AdministrationData,
    AgricultureData,
    CommerceData,
    ConsumptionData,
    MilitaryData,
    NationalBaseData,
    PopulationData,
    ProvinceBaseData,
    TaxationData,
    TradeData,
)

# RULE.md 缓存
_rule_cache: str | None = None


def load_rule_md(data_dir: Path | None = None) -> str:
    """加载 RULE.md 内容（带缓存）。

    Args:
        data_dir: 数据目录路径，默认为 data/

    Returns:
        RULE.md 的内容，文件不存在时返回空字符串
    """
    global _rule_cache
    if _rule_cache is not None:
        return _rule_cache

    rule_path = (data_dir or Path("data")) / "RULE.md"
    if rule_path.exists():
        _rule_cache = rule_path.read_text(encoding="utf-8")
    else:
        _rule_cache = ""

    return _rule_cache


class ConfigurationError(Exception):
    """data_scope.yaml 配置错误。"""


class SkillScope(BaseModel):
    """单个 skill 的数据权限范围。"""

    national: list[str] = []
    provinces: list[str] | Literal["all"] = []
    fields: list[str] = []


class DataScope(BaseModel):
    """Agent 的完整数据权限声明。"""

    display_name: str
    skills: dict[str, SkillScope]


class AgentContext(BaseModel):
    """组装好的 Agent 上下文，用于后续 LLM 调用。"""

    agent_id: str
    soul: str
    skill: str
    data: dict[str, Any]
    memory_summary: str | None = None
    recent_memories: list[tuple[int, str]] = []
    rule: str | None = None  # RULE.md 规范内容


# ── 字段注册表（从 ProvinceBaseData 内省构建）──

_SUBSYSTEM_MODELS: dict[str, type[BaseModel]] = {
    "population": PopulationData,
    "agriculture": AgricultureData,
    "commerce": CommerceData,
    "trade": TradeData,
    "military": MilitaryData,
    "taxation": TaxationData,
    "consumption": ConsumptionData,
    "administration": AdministrationData,
}

SUBSYSTEM_FIELDS: dict[str, list[str]] = {}
for _name, _model in _SUBSYSTEM_MODELS.items():
    SUBSYSTEM_FIELDS[_name] = [f.alias or name for name, f in _model.model_fields.items()]

PROVINCE_TOP_LEVEL_FIELDS = ["granary_stock", "local_treasury"]

NATIONAL_ALLOWED_FIELDS = ["imperial_treasury", "national_tax_modifier", "tribute_rate"]


# ── 字段解析 ──


def resolve_field_paths(field_specs: list[str]) -> list[str]:
    """将字段规格（含通配符）展开为具体字段路径列表。

    支持：
    - "commerce.*" → ["commerce.merchant_households", "commerce.market_prosperity"]
    - "commerce.merchant_households" → ["commerce.merchant_households"]
    - "granary_stock" → ["granary_stock"]

    Raises:
        ConfigurationError: 未知字段路径
    """
    resolved: list[str] = []

    for spec in field_specs:
        if "." in spec:
            subsystem, field_name = spec.split(".", 1)
            if subsystem not in SUBSYSTEM_FIELDS:
                raise ConfigurationError(f"Unknown subsystem: {subsystem}")

            if field_name == "*":
                # 通配符展开
                for f in SUBSYSTEM_FIELDS[subsystem]:
                    path = f"{subsystem}.{f}"
                    if path not in resolved:
                        resolved.append(path)
            else:
                # 精确匹配
                if field_name not in SUBSYSTEM_FIELDS[subsystem]:
                    raise ConfigurationError(
                        f"Unknown field: {spec} (valid fields for {subsystem}: "
                        f"{SUBSYSTEM_FIELDS[subsystem]})"
                    )
                path = f"{subsystem}.{field_name}"
                if path not in resolved:
                    resolved.append(path)
        else:
            # 顶层字段
            if spec not in PROVINCE_TOP_LEVEL_FIELDS:
                raise ConfigurationError(
                    f"Unknown top-level field: {spec} (valid: {PROVINCE_TOP_LEVEL_FIELDS})"
                )
            if spec not in resolved:
                resolved.append(spec)

    return resolved


# ── data_scope 解析 ──


def parse_data_scope(raw: dict[str, Any]) -> DataScope:
    """解析 data_scope.yaml 原始字典为 DataScope 对象。

    处理 inherits 机制（单层，检测循环/多级 → ConfigurationError）和
    additional_fields 合并 + 通配符展开。

    Raises:
        ConfigurationError: 配置错误（多级继承、循环依赖、未知字段等）
    """
    display_name = raw.get("display_name", "")
    raw_skills = raw.get("skills", {})

    # 第一遍：收集所有 skill 的原始定义，区分直接定义和继承
    direct_skills: dict[str, dict[str, Any]] = {}
    inheriting_skills: dict[str, dict[str, Any]] = {}

    for skill_name, skill_def in raw_skills.items():
        if skill_def is None:
            skill_def = {}
        if "inherits" in skill_def:
            inheriting_skills[skill_name] = skill_def
        else:
            direct_skills[skill_name] = skill_def

    # 第二遍：解析直接定义的 skill
    parsed_skills: dict[str, SkillScope] = {}
    for skill_name, skill_def in direct_skills.items():
        national = skill_def.get("national", [])
        # 验证 national 字段
        for n in national:
            if n not in NATIONAL_ALLOWED_FIELDS:
                raise ConfigurationError(f"Unknown national field: {n} in skill {skill_name}")

        provinces = skill_def.get("provinces", [])
        raw_fields = skill_def.get("fields", [])
        resolved = resolve_field_paths(raw_fields)

        parsed_skills[skill_name] = SkillScope(
            national=national,
            provinces=provinces,
            fields=resolved,
        )

    # 第三遍：解析继承的 skill
    for skill_name, skill_def in inheriting_skills.items():
        parent_name = skill_def["inherits"]

        # 检查循环依赖（自引用）
        if parent_name == skill_name:
            raise ConfigurationError(f"Circular inheritance: {skill_name} inherits from itself")

        # 检查父 skill 是否存在
        if parent_name not in parsed_skills:
            if parent_name in inheriting_skills:
                raise ConfigurationError(
                    f"Multi-level inheritance detected: {skill_name} inherits {parent_name} "
                    f"which also uses inherits"
                )
            raise ConfigurationError(
                f"Skill {skill_name} inherits from unknown skill: {parent_name}"
            )

        parent = parsed_skills[parent_name]

        # 复制父 skill 的定义
        national = list(parent.national)
        provinces = (
            parent.provinces if isinstance(parent.provinces, str) else list(parent.provinces)
        )
        fields = list(parent.fields)

        # 处理 additional_fields
        additional = skill_def.get("additional_fields", [])
        if additional:
            extra = resolve_field_paths(additional)
            # set 合并去重
            existing = set(fields)
            for f in extra:
                if f not in existing:
                    fields.append(f)
                    existing.add(f)

        parsed_skills[skill_name] = SkillScope(
            national=national,
            provinces=provinces,
            fields=fields,
        )

    return DataScope(display_name=display_name, skills=parsed_skills)


# ── 数据提取 ──


def extract_province_data(province: ProvinceBaseData, allowed_fields: list[str]) -> dict[str, Any]:
    """从省份数据中提取允许的字段子集。

    特殊处理 agriculture.crops 列表（序列化为 dict 列表）。
    """
    result: dict[str, Any] = {}

    for field_path in allowed_fields:
        if "." in field_path:
            subsystem, field_name = field_path.split(".", 1)
            sub_obj = getattr(province, subsystem, None)
            if sub_obj is None:
                continue

            if subsystem not in result:
                result[subsystem] = {}

            value = getattr(sub_obj, field_name, None)
            if value is None:
                continue

            # 特殊处理 crops 列表
            if field_name == "crops":
                result[subsystem][field_name] = [
                    {
                        "crop_type": str(c.crop_type),
                        "area_mu": str(c.area_mu),
                        "yield_per_mu": str(c.yield_per_mu),
                    }
                    for c in value
                ]
            else:
                result[subsystem][field_name] = str(value)
        else:
            # 顶层字段
            value = getattr(province, field_path, None)
            if value is not None:
                result[field_path] = str(value)

    return result


def extract_scoped_data(national_data: NationalBaseData, skill_scope: SkillScope) -> dict[str, Any]:
    """按 SkillScope 从 NationalBaseData 提取数据子集。

    Returns:
        {"national": {...}, "provinces": {"zhili": {...}, ...}}
    """
    result: dict[str, Any] = {}

    # 提取 national 级字段
    if skill_scope.national:
        national_dict: dict[str, Any] = {}
        for field_name in skill_scope.national:
            value = getattr(national_data, field_name, None)
            if value is not None:
                national_dict[field_name] = str(value)
        if national_dict:
            result["national"] = national_dict

    # 确定要提取的省份
    if skill_scope.fields:
        target_provinces: list[ProvinceBaseData] = []
        if skill_scope.provinces == "all":
            target_provinces = list(national_data.provinces)
        elif isinstance(skill_scope.provinces, list) and skill_scope.provinces:
            province_map = {p.province_id: p for p in national_data.provinces}
            target_provinces = [
                province_map[pid] for pid in skill_scope.provinces if pid in province_map
            ]

        if target_provinces:
            provinces_dict: dict[str, Any] = {}
            for province in target_provinces:
                pdata = extract_province_data(province, skill_scope.fields)
                if pdata:
                    provinces_dict[province.province_id] = pdata
            if provinces_dict:
                result["provinces"] = provinces_dict

    return result


# ── ContextBuilder ──


class ContextBuilder:
    """组装 LLM 调用上下文。"""

    def __init__(self, file_manager: FileManager) -> None:
        self.file_manager = file_manager

    def load_data_scope(self, agent_id: str) -> DataScope:
        """加载并解析 agent 的 data_scope.yaml。"""
        raw = self.file_manager.read_data_scope_raw(agent_id)
        return parse_data_scope(raw)

    def build_context(
        self,
        agent_id: str,
        skill_name: str,
        national_data: NationalBaseData,
        memory_summary: str | None = None,
        recent_memories: list[tuple[int, str]] | None = None,
    ) -> AgentContext:
        """组装完整的 Agent 上下文。

        Args:
            agent_id: Agent ID
            skill_name: 当前使用的 skill 名称
            national_data: 全国数据
            memory_summary: 长期记忆
            recent_memories: 短期记忆列表

        Returns:
            AgentContext 对象
        """
        soul = self.file_manager.read_soul(agent_id)
        data_scope = self.load_data_scope(agent_id)

        if skill_name not in data_scope.skills:
            raise ConfigurationError(
                f"Skill '{skill_name}' not found in data_scope for agent '{agent_id}'"
            )

        skill = self.file_manager.read_skill(skill_name)

        skill_scope = data_scope.skills[skill_name]
        data = extract_scoped_data(national_data, skill_scope)

        # 加载 RULE.md 规范
        rule = load_rule_md(self.file_manager.template_base.parent)

        return AgentContext(
            agent_id=agent_id,
            soul=soul,
            skill=skill,
            data=data,
            memory_summary=memory_summary,
            recent_memories=recent_memories or [],
            rule=rule if rule else None,
        )
