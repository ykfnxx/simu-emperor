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
                    "description": "省份 ID（如 'zhili', 'shanxi'）",
                    "enum": ["zhili", "shanxi", "jiangsu", "zhejiang", "fujian", "guangdong"],
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
        "name": "send_game_event",
        "description": "【执行动作】发送游戏事件到 Calculator。这是修改游戏状态的唯一方式！执行命令时必须调用此函数。",
        "parameters": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "description": "游戏事件类型\n- allocate_funds: 拨款（从国库拨给省库）\n- adjust_tax: 调整税率\n- build_irrigation: 建设水利\n- recruit_troops: 招募军队",
                    "enum": ["allocate_funds", "adjust_tax", "build_irrigation", "recruit_troops"],
                },
                "payload": {
                    "type": "object",
                    "description": "事件参数（根据 event_type 不同而不同）",
                    "properties": {
                        "province": {"type": "string", "description": "省份 ID"},
                        "amount": {"type": "number", "description": "金额（拨款时使用）"},
                        "rate": {"type": "number", "description": "税率（0-1）"},
                        "count": {"type": "integer", "description": "数量（士兵数等）"},
                    },
                },
            },
            "required": ["event_type", "payload"],
        },
    },
    {
        "name": "send_message_to_agent",
        "description": "发送消息给其他 Agent（如通知其他官员）",
        "parameters": {
            "type": "object",
            "properties": {
                "target_agent": {
                    "type": "string",
                    "description": "目标 Agent ID（如 'governor_zhili', 'minister_of_revenue'）",
                },
                "message": {"type": "string", "description": "消息内容"},
            },
            "required": ["target_agent", "message"],
        },
    },
    {
        "name": "respond_to_player",
        "description": "响应玩家（仅当事件来自玩家时使用）",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "响应内容（扮演风格，生动有趣）"}
            },
            "required": ["content"],
        },
    },
    {
        "name": "send_ready",
        "description": "发送 ready 信号（仅在 end_turn 事件时使用）",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "write_memory",
        "description": "写入记忆（仅在 turn_resolved 事件时使用）",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "总结内容（本回合发生的事情、重要决策和结果）",
                }
            },
            "required": ["content"],
        },
    },
]
