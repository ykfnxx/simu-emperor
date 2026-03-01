---
name: query_data
version: 1.0.0
description: 查询游戏数据
author: system
tags: [query, data]
parameters:
  province_id:
    type: str
    description: 省份ID
    required: true
  metric_type:
    type: str
    description: 指标类型
    required: false
---

这是一个用于查询游戏数据的 Skill。

## 使用方法

1. 选择要查询的省份
2. 选择要查看的指标类型
3. 返回查询结果

## 注意事项

- 需要提供有效的省份ID
- 指标类型可选
