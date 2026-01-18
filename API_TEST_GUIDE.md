# Province Agent API测试指南

## 配置系统说明

### 文件结构

```
/Users/yangkefan/workspace/simu-emperor/
├── config.yaml.example           # 配置模板（已提交到git）
├── config.yaml                   # 实际配置文件（不会被提交）
├── config_loader.py              # 配置加载模块
├── test_perception_agent_with_api.py   # API测试脚本
└── .gitignore                    # 保护敏感信息
```

### 快速开始

#### 1. 创建配置文件

```bash
# 复制配置模板
cp config.yaml.example config.yaml

# 编辑配置文件
vim config.yaml  # 或使用你喜欢的编辑器
```

#### 2. 配置API Key

有两种方式设置API key：

**方式1：直接在config.yaml中设置**
```yaml
llm:
  api_key: "sk-ant-api03-..."  # 你的Anthropic API key
```

**方式2：使用环境变量（推荐）**
```bash
# 在终端中设置
export ANTHROPIC_API_KEY=sk-ant-api03-...

# 或在~/.bashrc/~/.zshrc中添加
echo 'export ANTHROPIC_API_KEY=sk-ant-api03-...' >> ~/.bashrc
source ~/.bashrc
```

然后在config.yaml中使用：
```yaml
llm:
  api_key: "${ANTHROPIC_API_KEY}"
```

#### 3. 启用LLM

编辑config.yaml：
```yaml
llm:
  enabled: true        # 启用LLM
  mock_mode: false     # 关闭mock模式
  model: "claude-3-5-sonnet-20241022"  # 选择模型
```

#### 4. 运行测试

```bash
# 使用配置文件中的设置
python test_perception_agent_with_api.py

# 或直接指定API key（覆盖配置文件）
python test_perception_agent_with_api.py --api-key sk-ant-api03-...

# 强制使用mock模式（不调用API）
python test_perception_agent_with_api.py --mock
```

## 配置选项详解

### LLM配置

```yaml
llm:
  enabled: true                          # 是否启用LLM
  api_key: "${ANTHROPIC_API_KEY}"        # API密钥
  model: "claude-3-5-sonnet-20241022"   # 模型选择
  max_tokens: 4096                       # 最大token数
  temperature: 0.3                       # 温度（0-1）
  mock_mode: false                       # mock模式
```

**可用模型：**
- `claude-3-5-sonnet-20241022` - 最强，较慢，较贵
- `claude-3-5-haiku-20241022` - 快速，便宜，适合测试
- `claude-3-opus-20240229` - 旧版最强模型
- `claude-3-haiku-20240307` - 旧版快速模型

### Province Agent配置

```yaml
province_agent:
  enabled: true              # 启用Province Agent系统
  mode: "llm_assisted"       # 运行模式
  behavior:
    auto_execute: true       # 自动执行行为
    max_behaviors: 3         # 最大并行行为数
    risk_threshold: "medium"  # 风险阈值
```

**运行模式：**
- `rule_based` - 纯规则驱动（最快）
- `llm_assisted` - LLM辅助决策（需要API）

### PerceptionAgent配置

```yaml
perception_agent:
  history:
    monthly_months: 1        # 月度详细数据月数
    quarterly_quarters: 4    # 季度摘要季度数
    annual_years: 3          # 年度摘要年数

  critical_events:
    categories:              # 关键事件类别
      - rebellion
      - war
      - disaster
      - crisis
    max_events: 8            # 最大索引事件数

  summary:
    use_llm: true            # 使用LLM生成摘要
    max_length: 100          # 摘要长度限制
```

## 测试脚本说明

### test_perception_agent_with_api.py

使用真实LLM API测试PerceptionAgent的所有功能。

**功能：**
- 生成12个月测试数据
- 运行PerceptionAgent分析
- 调用LLM生成季度和年度摘要
- 输出趋势分析和风险评估
- 保存完整JSON结果

**输出：**
- 控制台：人类可读的结果摘要
- JSON文件：完整的PerceptionContext数据

**命令行参数：**
```bash
--config <path>      # 指定配置文件
--api-key <key>      # 直接提供API key
--mock               # 强制mock模式
```

## 配置加载示例

### Python代码中使用

```python
from config_loader import get_config, init_config

# 方式1：使用默认配置文件
config = get_config()

# 方式2：指定配置文件
config = init_config("my_config.yaml")

# 方式3：从命令行参数初始化
from config_loader import setup_config_from_args
config = setup_config_from_args()

# 获取配置值
llm_enabled = config.get('llm.enabled', False)
model = config.get('llm.model', 'claude-3-5-sonnet-20241022')

# 获取LLM配置（用于Agent）
llm_config = config.get_llm_config()

# 获取Province Agent配置
agent_config = config.get_province_agent_config(province_id=1)

# 检查LLM是否启用
if config.is_llm_enabled():
    print("LLM is enabled and configured")
else:
    print("Using mock mode")

# 修改配置
config.set('llm.enabled', True)
config.set('llm.temperature', 0.5)

# 保存配置
config.save("new_config.yaml")
```

## 安全最佳实践

### 1. 永远不要提交API Key

✅ **正确做法：**
```yaml
# config.yaml
api_key: "${ANTHROPIC_API_KEY}"  # 从环境变量读取
```

```bash
# 在终端或脚本中设置
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

❌ **错误做法：**
```yaml
# config.yaml
api_key: "sk-ant-api03-ABC123..."  # 永远不要直接写入
```

### 2. 使用环境变量

创建`.env`文件（已加入.gitignore）：
```bash
# .env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

加载环境变量：
```python
from dotenv import load_dotenv
load_dotenv()  # 自动加载.env文件
```

### 3. 限制API Key权限

- 为测试创建专用的API key
- 设置使用限额（spending limit）
- 定期轮换API key

### 4. 日志安全

配置文件已设置`.gitignore`忽略：
- `config.yaml` - 包含API key的配置文件
- `*.log` - 日志文件可能包含敏感数据
- `test_*.db` - 测试数据库

## 常见问题

### Q: 如何获取API Key？

A: 访问 https://console.anthropic.com/ 登录后获取

### Q: 测试时遇到API错误？

A: 检查：
1. API key是否正确
2. 账户是否有余额
3. 模型名称是否正确
4. 网络连接是否正常

### Q: 如何在mock模式和真实API之间切换？

A:
```yaml
# 方式1：修改配置文件
llm:
  mock_mode: true   # mock模式
  # mock_mode: false  # 真实API

# 方式2：命令行参数
python test_perception_agent_with_api.py --mock
```

### Q: 如何查看API调用详情？

A: 启用详细日志：
```yaml
logging:
  level: "DEBUG"
  verbose: true
```

### Q: 测试费用大约多少？

A:
- Mock模式：免费
- Haiku模型：约 $0.25/1M tokens（测试推荐）
- Sonnet模型：约 $3/1M tokens
- 单次测试约消耗 1000-2000 tokens，成本约 $0.001-0.01

## 下一步

1. **配置API Key**
   ```bash
   export ANTHROPIC_API_KEY=your-key-here
   ```

2. **编辑config.yaml启用LLM**
   ```yaml
   llm:
     enabled: true
     mock_mode: false
   ```

3. **运行测试**
   ```bash
   python test_perception_agent_with_api.py
   ```

4. **查看结果**
   - 控制台输出
   - `perception_context_api_test.json`

5. **调整配置**
   - 尝试不同模型
   - 调整temperature
   - 修改history窗口大小

祝测试顺利！🚀
