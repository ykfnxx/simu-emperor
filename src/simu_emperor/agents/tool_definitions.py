"""Agent Function Calling Tool 定义

此文件集中管理所有 Agent 可用的 Function Calling Tools，用于 LLM Function Calling。
这些 tools 定义了 Agent 可以调用的所有函数及其参数 schema。
"""

# 可用的 Functions（所有 Agent 共享）
AVAILABLE_FUNCTIONS = [
    {
        "name": "query_province_data",
        "description": "查询某个省份的特定数据字段（需要知道 province_id 和 field_path）",
        "parameters": {
            "type": "object",
            "properties": {
                "province_id": {
                    "type": "string",
                    "description": "省份 ID（如 'zhili', 'jiangsu'）",
                    "enum": [
                        "zhili",
                        "jiangsu",
                        "zhejiang",
                        "fujian",
                        "huguang",
                        "sichuan",
                        "shaanxi",
                        "shandong",
                        "jiangxi",
                    ],
                },
                "field_path": {
                    "type": "string",
                    "description": "数据字段路径（如 'population.total', 'agriculture.crops[0].yield'）",
                },
            },
            "required": ["province_id", "field_path"],
        },
    },
    {
        "name": "query_national_data",
        "description": "查询国家级数据（如国库、当前回合等）",
        "parameters": {
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "description": "字段名称（如 'imperial_treasury', 'turn'）",
                    "enum": ["imperial_treasury", "turn", "national_tax_modifier", "tribute_rate"],
                }
            },
            "required": ["field_name"],
        },
    },
    {
        "name": "list_provinces",
        "description": "列出所有可访问的省份 ID",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_agents",
        "description": "列出所有活跃的官员（Agent）及其职责",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "retrieve_memory",
        "description": "检索历史记忆。当玩家询问历史信息、之前的决策时使用。\n\n使用场景:\n- 玩家问'我之前做过什么'\n- 玩家问'给直隶拨过款吗'\n- 玩家提到'上次'、'之前'等时间词\n- 玩家询问过去的对话或事件",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "自然语言查询，如'我之前给直隶拨过款吗'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "最多返回几条结果（默认5）",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_agent_info",
        "description": "获取某个官员的详细信息（职责、性格等）",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "Agent ID（如 'governor_zhili', 'minister_of_revenue'）",
                }
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "send_message_to_agent",
        "description": "向其他官员发送消息（不能向自己发送），仅限于task中确认需要协调其他官员时使用（如需要其他官员执行某个操作）。不能主会话中直接调用此函数，应该在任务会话中调用以确保流程清晰。",
        "parameters": {
            "type": "object",
            "properties": {
                "target_agent": {
                    "type": "string",
                    "description": "目标 Agent ID（如 'governor_zhili', 'minister_of_revenue'）",
                },
                "message": {"type": "string", "description": "消息内容"},
                "await_reply": {
                    "type": "boolean",
                    "description": "是否等待对方回复。默认false（不等待），发送后继续处理。如果设为true，会暂停当前会话等待回复。",
                    "default": False,
                },
            },
            "required": ["target_agent", "message"],
        },
    },
    {
        "name": "respond_to_player",
        "description": """响应玩家（仅当事件来自玩家时使用）

⚠️ 极其重要的使用规则：
1. 必须是单次响应中最后一轮 agent loop 的唯一调用
2. 不能与任何其他工具同时调用（如 query_xxx、send_message_to_agent 等）
3. 如果需要执行其他操作，先在上一轮调用其他工具，然后在下一轮单独调用此工具
4. 违反此规则会导致其他工具被忽略，命令可能无法正确执行

正确模式：
- 第1轮：query_xxx(...) / send_message_to_agent(...)
- 第2轮：respond_to_player(...) ← 最后一轮，唯一调用
""",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "响应内容（扮演风格，生动有趣）"}
            },
            "required": ["content"],
        },
    },
    {
        "name": "finish_loop",
        "description": """结束当前 agent loop（仅当 session 有超过 2 个成员时生效）

⚠️ 使用规则：
1. 当你判断无需继续处理时，可调用此工具退出
2. 只有 session 成员数 > 2 时才会生效
3. 当成员数 ≤ 2 时，此工具不生效（防止只有一方在等待）

适用场景：
- 多人协商已达成结论，无需继续
- 你已收到足够的回复，可以结束讨论
- 其他 agent 都已表达意见，无需再等待

❌ 不适用场景：
- 1对1对话（请正常使用 respond_to_player）
- 只有 2 人的 session（此工具不生效）
""",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "退出循环的原因",
                },
            },
            "required": ["reason"],
        },
    },
    {
        "name": "create_task_session",
        "description": "创建一个任务会话（Task Session），用于需要等待其他 Agent 回复的复杂任务。parent_session 自动为当前 session，嵌套深度上限为 5 层。返回 task_session_id，需要在后续 finish/fail 时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "timeout_seconds": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 300 秒",
                    "default": 300,
                },
                "description": {"type": "string", "description": "任务描述，用于日志和调试"},
                "goal": {"type": "string", "description": "任务目标：清晰描述任务要达成什么结果"},
                "constraints": {
                    "type": "string",
                    "description": "成功约束：描述任务成功的判断标准或限制条件",
                },
            },
            "required": [],
        },
    },
    {
        "name": "finish_task_session",
        "description": "完成当前任务会话，将状态设置为 FINISHED（会自动识别当前会话，无需提供 task_session_id）",
        "parameters": {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "任务结果描述"},
            },
            "required": ["result"],
        },
    },
    {
        "name": "fail_task_session",
        "description": "标记当前任务会话为失败（会自动识别当前会话，无需提供 task_session_id）",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "失败原因"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "create_incident",
        "description": "创建持续 N 个 tick 的游戏事件。add 影响数值（一次性），factor 影响变化率（持续）",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "事件标题"},
                "description": {"type": "string", "description": "事件描述"},
                "effects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "target_path": {"type": "string", "description": "目标路径"},
                            "add": {
                                "type": "number",
                                "description": "一次性数值变化（仅影响 stockpile/treasury）",
                            },
                            "factor": {
                                "type": "number",
                                "description": "持续比例变化（仅影响 production_value/population）",
                            },
                        },
                        "required": ["target_path"],
                    },
                },
                "duration_ticks": {"type": "integer", "minimum": 1, "description": "持续 tick 数"},
            },
            "required": ["title", "description", "effects", "duration_ticks"],
        },
    },
]
