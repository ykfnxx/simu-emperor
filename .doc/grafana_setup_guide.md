# Grafana 可视化配置指南

本文档介绍如何配置 Grafana 来可视化 simu-emperor 的 LLM API 调用指标。

---

## 前置条件

1. **simu-emperor 服务运行中**
   ```bash
   uv run simu-emperor
   ```
   服务启动后，Prometheus 指标端点位于 `http://localhost:8000/metrics`

2. **Grafana 已安装**
   - macOS: `brew install grafana`
   - Docker: `docker run -d -p 3000:3000 grafana/grafana`
   - 其他平台: https://grafana.com/grafana/download

---

## 配置步骤

### 步骤 1: 启动 Grafana

**macOS (Homebrew)**:
```bash
brew services start grafana
```

**Docker**:
```bash
docker run -d --name=grafana -p 3000:3000 grafana/grafana
```

访问 http://localhost:3000，默认登录：
- 用户名: `admin`
- 密码: `admin`（首次登录会提示修改）

---

### 步骤 2: 添加 Prometheus 数据源

1. 左侧菜单 → **Connections** → **Data sources**
2. 点击 **Add data source**
3. 选择 **Prometheus**
4. 配置：
   - **Name**: `Simu-Emperor`（或任意名称）
   - **URL**: `http://host.docker.internal:8000`（Docker 方式）
     或 `http://localhost:8000`（本地安装方式）
   - **Scrape interval**: `5s`（可选，更频繁的抓取）

5. 点击 **Save & Test**，应显示 "Successfully queried the Prometheus API"

> **注意**: Docker 容器内访问宿主机，使用 `host.docker.internal` 而非 `localhost`

---

### 步骤 3: 导入 Dashboard

**方式 A: 通过界面导入**

1. 左侧菜单 → **Dashboards**
2. 点击 **New** → **Import**
3. 选择 **Upload dashboard JSON file**
4. 选择 `grafana/dashboard.json` 文件
5. 在 "Prometheus" 下拉框选择刚创建的数据源
6. 点击 **Import**

**方式 B: 通过 API 导入**

```bash
# 假设 Grafana 运行在 localhost:3000，admin/admin
curl -X POST \
  -u admin:admin \
  -H "Content-Type: application/json" \
  -d @grafana/dashboard.json \
  http://localhost:3000/api/dashboards/db
```

---

### 步骤 4: 查看 Dashboard

导入成功后，Dashboard 显示以下面板：

| 面板 | 说明 |
|------|------|
| **总调用次数** | 所有成功的 LLM 调用数 |
| **成功率** | 成功调用占总调用的比例 |
| **总 Token 消耗** | Prompt + Completion tokens 总和 |
| **累计成本** | 基于配置价格的估算成本（美元） |
| **P95 延迟** | 95% 的调用响应时间低于此值 |
| **调用频率（按 Agent）** | 各 Agent 的调用速率时序图 |
| **延迟分布** | P50/P95/P99 延迟趋势 |
| **调用分布（按 Agent）** | 各 Agent 调用占比饼图 |
| **调用分布（按阶段）** | summarize/respond/execute 占比 |
| **Token 消耗速率** | Prompt/Completion tokens 速率 |

---

## 配置 Prometheus 抓取（可选）

如果需要 Prometheus 服务器来抓取指标（而非 Grafana 直接读取）：

### prometheus.yml

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'simu-emperor'
    static_configs:
      - targets: ['host.docker.internal:8000']  # Docker
        # 或 ['localhost:8000']  # 本地
```

### 启动 Prometheus

```bash
docker run -d \
  --name prometheus \
  -p 9090:9090 \
  -v $(pwd)/prometheus.yml:/etc/prometheus/prometheus.yml \
  prom/prometheus
```

然后在 Grafana 中配置数据源 URL 为 `http://prometheus:9090`（Docker 网络）或 `http://localhost:9090`（本地）

---

## 可用指标

| 指标名 | 类型 | 说明 |
|--------|------|------|
| `llm_calls_total` | Counter | LLM 调用总数，按 provider/model/agent_id/phase/status 分类 |
| `llm_tokens_total` | Counter | Token 消耗，按 provider/model/type(prompt/completion) 分类 |
| `llm_call_duration_seconds` | Histogram | 调用延迟（秒），自动计算 P50/P90/P95/P99 |
| `llm_cost_usd_total` | Counter | 累计成本（美元） |
| `game_current_turn` | Gauge | 当前游戏回合 |

---

## 常用 PromQL 查询

```promql
# 总调用次数
sum(llm_calls_total)

# 成功率
sum(llm_calls_total{status="success"}) / sum(llm_calls_total)

# 按 Agent 的调用次数
sum by (agent_id) (llm_calls_total)

# 按阶段的调用次数
sum by (phase) (llm_calls_total)

# P95 延迟
histogram_quantile(0.95, sum(rate(llm_call_duration_seconds_bucket[5m])) by (le))

# 每分钟调用速率
rate(llm_calls_total[1m])

# 总 Token 消耗
sum(llm_tokens_total)

# 累计成本
sum(llm_cost_usd_total)
```

---

## 故障排查

### 指标端点无法访问

1. 确认 simu-emperor 服务正在运行
2. 测试指标端点：
   ```bash
   curl http://localhost:8000/metrics
   ```
3. 检查端口是否被占用

### Grafana 无法连接数据源

1. **Docker 环境**: 使用 `host.docker.internal` 而非 `localhost`
2. **防火墙**: 确保 8000 端口可访问
3. **网络**: 检查 Docker 网络配置

### Dashboard 显示 "No Data"

1. 确认 LLM 调用已发生（调用后才有数据）
2. 检查时间范围（右上角设置为 "Last 1 hour"）
3. 验证数据源连接正常

### 成本显示为 0

1. 检查 `config.yaml` 中的 `pricing` 配置
2. 确认使用的是配置中定义的 provider/model 名称

---

## 成本配置

在 `config.yaml` 中配置价格（每 1M tokens，美元）：

```yaml
logging:
  metrics_enabled: true
  pricing:
    anthropic:
      claude-sonnet-4:
        prompt: 3.0      # $3/1M prompt tokens
        completion: 15.0  # $15/1M completion tokens
      claude-opus-4:
        prompt: 15.0
        completion: 75.0
    openai:
      gpt-4o:
        prompt: 2.5
        completion: 10.0
      gpt-4o-mini:
        prompt: 0.15
        completion: 0.6
```

价格参考：
- Anthropic: https://www.anthropic.com/pricing
- OpenAI: https://openai.com/pricing
