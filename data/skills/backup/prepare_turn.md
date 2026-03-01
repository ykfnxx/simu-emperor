# 准备回合

## 能力说明
回合即将结束，你需要：
1. 准备下一回合的工作
2. 发送 ready 信号给系统

## 输出格式
你的输出必须包含 actions，其中至少包含一个 ready action：
```json
{
    "narrative": "准备就绪",
    "actions": [
        {
            "type": "ready",
            "target": "system:calculator"
        }
    ]
}
```
