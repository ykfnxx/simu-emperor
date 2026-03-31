"""Agent 配置生成器 - 使用 LLM 生成 soul.md 和 data_scope.yaml

此模块提供运行时动态生成 agent 配置文件的功能。
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simu_emperor.llm.base import LLMProvider


logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """Agent 配置输入参数

    Attributes:
        agent_id: Agent 唯一标识符（如 governor_zhili）
        title: 官职（如 "直隶巡抚"）
        name: 姓名（如 "蔡珽"）
        duty: 职责描述（如 "直隶省民政、农桑、商贸、治安"）
        personality: 为人描述（如 "行事果断，忠心耿耿"）
        province: 管辖省份（可选，如 "zhili"）
    """

    agent_id: str
    title: str
    name: str
    duty: str
    personality: str
    province: str | None = None


@dataclass
class GeneratedConfig:
    """LLM 生成的配置文件内容

    Attributes:
        soul_md: soul.md 文件内容
        data_scope: data_scope.yaml 文件内容
        role_map_entry: role_map.md 追加条目
    """

    soul_md: str
    data_scope: str
    role_map_entry: str


class AgentGenerator:
    """使用 LLM 生成 agent 配置文件

    根据用户提供的基础信息（官职、姓名、职责、为人），
    通过 LLM 生成完整的 soul.md 和 data_scope.yaml 配置文件。
    """

    def __init__(self, llm_provider: "LLMProvider", data_dir: Path) -> None:
        """初始化 AgentGenerator

        Args:
            llm_provider: LLM 提供商实例
            data_dir: 数据目录路径
        """
        self.llm_provider = llm_provider
        self.data_dir = data_dir

    async def generate_config(self, config: AgentProfile) -> GeneratedConfig:
        """生成完整的 agent 配置

        Args:
            config: Agent 配置输入参数

        Returns:
            GeneratedConfig: 包含 soul_md, data_scope, role_map_entry

        Raises:
            ValueError: LLM 响应解析失败
        """
        prompt = self._build_generation_prompt(config)
        system_prompt = self._build_system_prompt()

        logger.info(f"Generating config for agent {config.agent_id}...")

        response = await self.llm_provider.call(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=3000,
        )

        logger.debug(f"LLM response for {config.agent_id}: {response[:200]}...")

        return self._parse_response(response, config)

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是大清帝国的官员档案编写员。你的任务是根据提供的基础信息，生成完整的官员配置文件。

你必须严格按照以下 YAML 格式输出，不要添加任何额外文字：

```yaml
soul_md: |
  # {title} - {name}

  ## 身份
  你是大清{title}{name}，{duty}

  ## 性格
  - {性格特点1}
  - {性格特点2}
  - {性格特点3}
  - {性格特点4}

  ## 行为倾向
  - {行为倾向1}
  - {行为倾向2}
  - {行为倾向3}

  ## 说话风格
  {说话风格描述}

data_scope: |
  display_name: {title}

  skills:
    query_data:
      provinces: [{province_list}]
      fields:
        - population.*
        - agriculture.*
        - commerce.*
        - trade.*
        - granary_stock
        - local_treasury

    write_report:
      inherits: query_data

    execute_command:
      provinces: [{province_list}]
      fields:
        - agriculture.irrigation_level
        - taxation.commercial_tax_rate
        - granary_stock

role_map_entry: |
  ## {title} ({agent_id})
  - 姓名：{name}
  - 职责：{duty}
  - 适用命令：{applicable_commands}
  - 为人：{personality}
```

注意：
1. soul_md 中性格特点要扩展为 4 个具体描述
2. 行为倾向要体现该官员如何处理政务、是否诚实、是否欺瞒等
3. 说话风格要符合其身份地位
4. data_scope 中的 province_list 根据管辖地区决定，单省用省名，全国用 all
5. 适用命令要与其职责相关，列举 4-6 个
6. 为人描述保持用户提供的原文或稍作润色
"""

    def _build_generation_prompt(self, config: AgentProfile) -> str:
        """构建用户提示词"""
        province_hint = f"，管辖{config.province}省" if config.province else "，管辖全国"
        return f"""请为以下官员生成完整的配置文件：

**官职**: {config.title}
**姓名**: {config.name}
**职责**: {config.duty}
**为人**: {config.personality}
**管辖**: {config.province or "全国"}{province_hint}

要求：
1. 根据为人描述，扩展出 4 个具体的性格特点
2. 行为倾向要体现该官员如何处理政务、是否诚实、是否欺瞒等
3. 说话风格要符合其身份地位
4. 适用命令要与其职责相关，列举 4-6 个
5. 如果是地方官，data_scope 中只列出其管辖省份；如果是中央官员，使用 all

请严格按照输出格式返回。"""

    def _parse_response(self, response: str, config: AgentProfile) -> GeneratedConfig:
        """解析 LLM 返回的 YAML 格式响应

        Args:
            response: LLM 返回的文本
            config: 原始配置参数

        Returns:
            GeneratedConfig: 解析后的配置

        Raises:
            ValueError: 解析失败
        """
        # 尝试解析 YAML 格式
        try:
            import yaml

            # 提取 YAML 代码块（如果存在）
            yaml_match = re.search(r"```yaml\s*\n(.*?)\n```", response, re.DOTALL)
            if yaml_match:
                yaml_content = yaml_match.group(1)
            else:
                # 如果没有代码块，尝试直接解析
                yaml_content = response.strip()

            data = yaml.safe_load(yaml_content)

            soul_md = data.get("soul_md", "")
            data_scope = data.get("data_scope", "")
            role_map_entry = data.get("role_map_entry", "")

            if not soul_md or not data_scope or not role_map_entry:
                raise ValueError("Missing required fields in LLM response")

            return GeneratedConfig(
                soul_md=soul_md,
                data_scope=data_scope,
                role_map_entry=role_map_entry,
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # 返回默认配置作为降级处理
            return self._generate_fallback_config(config)

    def _generate_fallback_config(self, config: AgentProfile) -> GeneratedConfig:
        """生成降级配置（当 LLM 解析失败时使用）"""
        logger.warning(f"Using fallback config for agent {config.agent_id}")

        # 确定省份列表
        if config.province:
            province_list = f"[{config.province}]"
        else:
            province_list = "[all]"

        # 生成 soul.md
        soul_md = f"""# {config.title} - {config.name}

## 身份
你是大清{config.title}{config.name}，{config.duty}

## 性格
- {config.personality}
- 办事勤勉，忠于职守
- 处事谨慎，谨言慎行
- 关注民生，体恤百姓

## 行为倾向
- 汇报时较为诚实，但会根据情况选择表达方式
- 执行命令时尽力而为，遇困难会及时上报
- 与同僚保持良好关系，注重协调

## 说话风格
言辞得体，符合官员身份，奏折格式规范。
"""

        # 生成 data_scope.yaml
        data_scope = f"""display_name: {config.title}

skills:
  query_data:
    provinces: {province_list}
    fields:
      - population.*
      - agriculture.*
      - commerce.*
      - trade.*
      - granary_stock
      - local_treasury

  write_report:
    inherits: query_data

  execute_command:
    provinces: {province_list}
    fields:
      - agriculture.irrigation_level
      - taxation.commercial_tax_rate
      - granary_stock
"""

        # 生成 role_map_entry
        role_map_entry = f"""## {config.title} ({config.agent_id})
- 姓名：{config.name}
- 职责：{config.duty}
- 适用命令：地方治理、民情上报
- 为人：{config.personality}
"""

        return GeneratedConfig(
            soul_md=soul_md,
            data_scope=data_scope,
            role_map_entry=role_map_entry,
        )
