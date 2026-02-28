# 总结回合

## 能力说明
回合结算完成，你需要：
1. 总结本回合发生的事情
2. 记录重要决策和结果
3. 写入记忆供将来参考

## 输出格式
你的输出必须包含 actions，其中包含一个 write_memory action：
```json
{
    "narrative": "回合总结",
    "actions": [
        {
            "type": "write_memory",
            "content": "本回合的详细总结..."
        }
    ]
}
```
