"""LLM Task Type 常量定义（V4.3）

定义 6 种粗粒度的 task_type，用于 LLM 配置系统。
"""


class LLMTaskType:
    """LLM 任务类型常量"""

    AGENT_RESPONSE = "agent_response"           # Agent 响应玩家交互
    MEMORY_SUMMARIZE = "memory_summarize"       # Memory 系统摘要生成
    TITLE_GENERATION = "title_generation"       # Session 标题生成
    INCIDENT_BEAUTIFY = "incident_beautify"     # Incident 叙事美化
    AUTONOMOUS_REFLECTION = "autonomous_reflection"  # Tick 反思自主记忆
    QUERY_PARSING = "query_parsing"             # 查询解析（retrieve_memory）

    @classmethod
    def all(cls) -> list[str]:
        """获取所有任务类型"""
        return [
            cls.AGENT_RESPONSE,
            cls.MEMORY_SUMMARIZE,
            cls.TITLE_GENERATION,
            cls.INCIDENT_BEAUTIFY,
            cls.AUTONOMOUS_REFLECTION,
            cls.QUERY_PARSING,
        ]
