# Province Agent 实施路线图

## 一、实现目标

### 1.1 核心目标

构建一个智能化的Province Agent系统，使其能够：

1. **历史数据理解**
   - 读取并分析省份历史数据（收入、支出、忠诚度、稳定性等）
   - 识别长期趋势和周期性模式
   - 检测异常情况和关键事件

2. **指令执行**
   - 接收玩家的治理指令（如提高税收、投资建设、降低支出）
   - 评估指令的可行性和风险
   - 根据省份实际情况调整执行参数和力度

3. **主动行为**
   - 在无指令时，根据历史趋势和当前状态自主做出决策
   - 优先处理紧急问题（低忠诚度、低稳定性、经济危机）
   - 制定长期发展策略

4. **结果反馈**
   - 执行行为后生成结算报告（三层数据：actual → adjusted → reported）
   - 生成行为事件并上报给玩家
   - 记录行为历史用于未来决策参考

### 1.2 与现有系统的关系

**现有系统：**
- GovernorAgent：负责腐败/诚实决策，决定reporting_bias_ratio
- Event系统：负责事件的生成、管理和效果计算
- 三层数据模型：actual → adjusted → reported

**Province Agent定位（三层架构）：**
- **PerceptionAgent**：数据感知层，负责历史数据分析和趋势识别
- **DecisionAgent**：决策层，基于感知信息制定行为策略  
- **ExecutionAgent**：执行层，负责行为实施和效果计算
- **与GovernorAgent协作**：新架构处理主动治理，GovernorAgent专注数据瞒报
- **增强游戏智能**：提供更真实的地方治理模拟和玩家交互

**协作关系（串行依赖流程）：**
```
【严格的串行依赖顺序】

① 感知阶段（必须首先执行）
PerceptionAgent
  ↓ 依赖：历史数据（月度/季度/年度记录 + 关键事件索引）
  ↓ 处理：数据收集 → 趋势分析 → 风险识别
  ↓ 输出：PerceptionContext（感知上下文）
  ↓ 阻塞：DecisionAgent必须等待感知完成

② 决策阶段（依赖感知结果）  
DecisionAgent
  ↓ 依赖：PerceptionContext + 玩家指令（可选）
  ↓ 处理：策略评估 → 行为选择 → 参数优化 → 风险评估
  ↓ 输出：Decision（含behaviors行为列表）
  ↓ 阻塞：ExecutionAgent必须等待决策完成

③ 执行阶段（依赖决策结果）
ExecutionAgent
  ↓ 依赖：Decision + 当前省份状态
  ↓ 处理：行为执行 → 效果计算 → 属性修改 → 事件生成
  ↓ 输出：修改后的actual数据 + 生成的事件
  ↓ 阻塞：GovernorAgent必须等待执行完成

④ 数据瞒报阶段（依赖执行结果）
GovernorAgent (现有系统)
  ↓ 依赖：ExecutionAgent修改后的actual数据
  ↓ 处理：瞒报决策 → 数据调整 → reported生成
  ↓ 输出：三层数据（actual/adjusted/reported）
  ↓ 注意：瞒报逻辑独立于新Agent行为，保持现有决策机制

⑤ 事件反馈阶段（依赖所有前置结果）
Event System
  ↓ 依赖：ExecutionAgent生成的事件 + GovernorAgent的瞒报结果
  ↓ 处理：事件记录 → 状态更新 → 数据持久化
  ↓ 输出：更新的游戏状态 → 为下月感知提供新数据
  ↓ 完成：闭环，为下次循环做准备

【关键约束】
✗ 不可并行：每个阶段必须等待前一阶段完成
✗ 不可跳过：感知 → 决策 → 执行是强制顺序
✓ 错误处理：任一阶段失败需有回退机制
✓ 数据一致性：确保actual数据在GovernorAgent处理前已更新
```

---

## 二、系统架构设计

### 2.1 整体架构

Province Agent采用**感知-决策-执行** (Perception-Decision-Execution) 的经典三层Agent架构：

**核心特征 - 串行依赖流程：**
与并行架构不同，本设计采用**严格的串行依赖模式**：
- **感知 → 决策 → 执行**：每个阶段必须等待前一阶段完成
- **不可跳过**：没有感知结果就无法做决策，没有决策就无法执行
- **数据单向流动**：每个阶段接收前一阶段的输出作为输入
- **错误传播**：任一阶段失败都会影响整个流程

**架构原则：**
- **感知层 (PerceptionAgent)**：负责数据收集、历史分析、趋势识别和风险评估
- **决策层 (DecisionAgent)**：基于感知信息、玩家指令和预设规则做出行为决策
- **执行层 (ExecutionAgent)**：负责行为效果计算、事件生成、结果记录和反馈
- **串行执行**：三个Agent按固定顺序执行，形成pipeline模式
- **数据完整性**：保留现有的三层数据模型 (actual → adjusted → reported)
- **协同工作**：新Agent架构与现有GovernorAgent协同，GovernorAgent专注于数据瞒报处理
- **时序明确**：感知→决策→执行→瞒报处理→事件反馈，形成完整闭环

**设计权衡：**
- ✅ **可预测性**：串行流程易于理解和调试
- ✅ **数据一致性**：避免竞态条件，确保状态一致性
- ✅ **错误追踪**：清晰的错误传播路径
- ❌ **性能开销**：无法并行化，总延迟为各阶段之和
- ❌ **单点故障**：任一阶段失败会导致整个流程中断
- ❌ **扩展性限制**：难以通过并行化提升性能

**缓解策略：**
- 每个阶段设置超时机制
- 实现优雅降级（失败时回退到简单规则）
- 缓存机制减少重复计算
- 异步执行（在阶段内部，非阶段间）

```
【感知-决策-执行架构图 - 串行依赖流程】

┌─────────────────────────────────────────────────────────────────────────┐
│                              Game Loop                                  │
│                          (core/game.py)                                 │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │  历史数据输入    │ ←─ 数据库中的历史记录
                │  (月度/季度/年度) │ ←─ 关键事件索引
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ PerceptionAgent │ ◄── 感知阶段
                │   (感知Agent)    │    - 数据收集
                │                 │    - 趋势分析  
                │                 │    - 风险识别
                └────────┬────────┘
                         │
                         │ 输出: PerceptionContext
                         ▼
                ┌─────────────────┐
                │ DecisionAgent   │ ◄── 决策阶段  
                │   (决策Agent)    │    - 接收感知上下文
                │                 │    - 评估玩家指令
                │                 │    - 制定行为策略
                └────────┬────────┘
                         │
                         │ 输出: Decision (behaviors列表)
                         ▼
                ┌─────────────────┐
                │ ExecutionAgent  │ ◄── 执行阶段
                │   (执行Agent)    │    - 执行具体行为
                │                 │    - 计算效果
                │                 │    - 生成事件
                └────────┬────────┘
                         │
                         │ 输出: 修改后的actual数据
                         ▼
                ┌─────────────────┐
                │ GovernorAgent   │ ◄── 数据瞒报阶段
                │ (现有瞒报系统)   │    - 接收actual数据
                │                 │    - 决定是否瞒报
                │                 │    - 生成reported数据
                └────────┬────────┘
                         │
                         │ 输出: reported数据
                         ▼
                ┌─────────────────┐
                │   三层数据模型   │ ◄── 数据整合
                │ actual → adjusted │    - 保持数据一致性
                │        → reported │    - 支持审计追踪
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │  Event System   │ ◄── 事件反馈
                │  (事件记录)     │    - 记录行为事件
                │                 │    - 更新游戏状态
                │                 │    - 为下月提供数据
                └─────────────────┘

【核心特征】
✓ 串行依赖：感知 → 决策 → 执行 → 瞒报 → 反馈
✓ 数据单向流动：每个阶段接收前一阶段的输出
✓ 与现有系统兼容：GovernorAgent位置不变，专注瞒报
✓ 闭环设计：事件反馈为下月感知提供输入
```

### 2.2 历史数据管理策略

**问题：** 长期历史数据会导致上下文过长，影响Agent决策效率

**解决方案：** 分层滑动窗口 + 关键事件索引

#### 2.2.1 分层结构

```
┌──────────────────────────────────────────────────────────────┐
│                    近1个月（详细数据）                         │
│  - 完整的月度数据（收入、支出、忠诚度、稳定性、事件详情）      │
│  - 上个月的具体数值和事件                                      │
│  - 用途：短期决策参考，了解当前状态                            │
├──────────────────────────────────────────────────────────────┤
│                    近4季度（摘要数据）                         │
│  - 每季度聚合数据（均值、中位数、趋势）                         │
│  - 季度内关键事件列表                                          │
│  - 用途：中期趋势分析，识别季节性模式                          │
├──────────────────────────────────────────────────────────────┤
│                    近3年（摘要数据）                           │
│  - 年度聚合数据（总收入、总支出、平均表现）                     │
│  - 年度重大事件索引（只记录特殊事件）                          │
│  - 用途：长期战略参考，识别发展周期                            │
├──────────────────────────────────────────────────────────────┤
│                    关键事件索引                               │
│  - 独立索引表，只记录特殊事件（叛乱、战争、灾难）               │
│  - 快速检索历史危机及应对策略                                  │
│  - 用途：异常情况参考，风险预警                                │
└──────────────────────────────────────────────────────────────┘
```

#### 2.2.2 数据流转

**月度流程：**
```
1. 月初：PerceptionAgent读取上个月完整数据
2. 月末：ExecutionAgent生成本月月度摘要并保存

季度末（3, 6, 9, 12月）：
1. PerceptionAgent检查是否需要生成季度摘要
2. 如果没有，则基于3个月的数据聚合生成
3. 保存到province_quarterly_summaries表

年末（12月）：
1. PerceptionAgent生成年度摘要
2. 清理过期数据（删除3年前的月度详细数据）
3. 保留所有季度和年度摘要
```

#### 2.2.3 Token预算控制

假设总token预算为4000：

```
近期详细数据（1个月）：1600 tokens (40%)
  - 完整的数值、事件、决策记录

历史摘要（4季度+3年）：1600 tokens (40%)
  - 4个季度摘要 × 200 tokens = 800 tokens
  - 3个年度摘要 × 200 tokens = 600 tokens
  - 趋势分析 = 200 tokens

关键事件索引：800 tokens (20%)
  - 近12个月内的特殊事件（叛乱、战争、灾难）
  - 每个事件约100 tokens，最多8个事件
```

### 2.3 三个Agent的详细设计

#### 2.3.1 PerceptionAgent（感知Agent）

**职责：**
1. 读取历史数据（月度、季度、年度）
2. 生成分层摘要
3. 索引关键事件
4. 分析趋势（收入、支出、忠诚度、稳定性）
5. 识别异常和风险

**输入：**
- province_id: int
- current_month: int
- current_year: int

**处理流程：**
```
1. 从数据库读取上个月完整数据
   - 查询monthly_reports表
   - 查询provinces表获取当前状态
   - 查询events表获取上月事件

2. 构建季度摘要（近4个季度）
   - 如果季度摘要已存在，直接读取
   - 如果不存在，基于月度数据聚合生成
   - 计算统计指标：均值、中位数、趋势

3. 构建年度摘要（近3年）
   - 如果年度摘要已存在，直接读取
   - 如果不存在，基于季度或月度数据聚合生成
   - 计算年度统计：总收入、总支出、年度变化

4. 索引关键事件
   - 查询special_events_index表
   - 只获取特殊事件类型（叛乱、战争、灾难、危机）
   - 按时间倒序排列

5. 分析趋势
   - 对比最近两个季度的数据
   - 判断趋势方向：increasing / stable / decreasing
   - 评估风险级别：low / medium / high
```

**输出：PerceptionContext**
```python
class PerceptionContext(BaseModel):
    province_id: int
    current_month: int
    current_year: int

    # 近期详细数据
    recent_data: MonthlyDetailedData

    # 历史摘要
    quarterly_summaries: List[QuarterlySummary]  # 近4个季度
    annual_summaries: List[AnnualSummary]        # 近3年

    # 关键事件索引
    critical_events: List[EventIndex]

    # 趋势分析
    trends: TrendAnalysis

class MonthlyDetailedData(BaseModel):
    month: int
    year: int
    population: int
    development_level: float
    loyalty: float
    stability: float
    actual_income: float
    actual_expenditure: float
    reported_income: float
    reported_expenditure: float
    events: List[EventSummary]

class QuarterlySummary(BaseModel):
    quarter: int
    year: int
    avg_income: float
    median_income: float
    avg_expenditure: float
    total_surplus: float
    income_trend: str  # 'increasing' | 'stable' | 'decreasing'
    major_events: List[str]
    special_event_types: List[str]

class AnnualSummary(BaseModel):
    year: int
    total_income: float
    total_expenditure: float
    avg_monthly_income: float
    avg_monthly_expenditure: float
    total_surplus: float
    population_change: int
    development_change: float
    loyalty_start: float
    loyalty_end: float
    loyalty_change: float

class TrendAnalysis(BaseModel):
    income_trend: str
    expenditure_trend: str
    loyalty_trend: str
    stability_trend: str
    risk_level: str  # 'low' | 'medium' | 'high'
```

**关键方法实现：**

1. `_build_monthly_detailed()`
   - 从monthly_reports表查询上月数据
   - 从provinces表查询当前状态
   - 从events表查询上月事件
   - 如果没有历史数据，返回默认值

2. `_build_quarterly_summaries()`
   - 计算当前季度
   - 尝试从province_quarterly_summaries表读取
   - 如果不存在，调用_generate_quarterly_summary()
   - 返回近4个季度的摘要

3. `_generate_quarterly_summary()`
   - 计算季度月份范围（如Q1 = 1-3月）
   - 从monthly_reports表查询季度数据
   - 计算统计指标：AVG、MEDIAN、SUM
   - 对比上个季度判断趋势
   - 保存到数据库以便复用

4. `_index_critical_events()`
   - 查询special_events_index表
   - 过滤特殊事件类型
   - 按时间倒序排列
   - 限制返回数量（如最多8个）

5. `_analyze_trends()`
   - 对比最近两个季度的均值
   - 计算变化率
   - 判断趋势方向（变化率 > 10% = increasing/decreasing）
   - 评估风险级别

#### 2.3.2 DecisionAgent（决策Agent）

**职责：**
1. 接收PerceptionContext和玩家指令
2. 评估指令可行性（忠诚度、国库、稳定性）
3. 选择行为类型（从预定义模板）
4. 决定行为参数（Agent在合理范围内自主决定）
5. 验证参数合法性
6. 评估风险

**输入：**
- perception: PerceptionContext
- instruction: Optional[PlayerInstruction]
- province_state: Dict[str, Any]

**决策逻辑：**

**情况1：有玩家指令**
```
1. 评估指令可行性
   - 检查前置条件（忠诚度、国库、稳定性）
   - 判断是否在合理范围

2. 如果可行
   - 决定执行力度（参数化：如提高税收5%-15%）
   - 创建主要行为（响应指令）

3. 如果不可行
   - 生成修改建议（降低幅度、延迟执行）
   - 或转为自主决策

4. 添加辅助行为
   - 如果主要行为有副作用，添加补偿行为
   - 例如：提高税收 → 降低忠诚度 → 添加忠诚度建设行为
```

**情况2：无玩家指令**
```
1. 分析趋势和风险
   - 如果收入下降 → 考虑税收调整
   - 如果忠诚度低 → 优先忠诚度建设
   - 如果稳定性低 → 优先稳定性提升
   - 如果都正常 → 选择发展性行为（基础设施投资）

2. 优先级排序
   - 紧急问题（忠诚度 < 60 或稳定性 < 60）优先
   - 次要问题（收入下降）次之
   - 发展行为最后

3. 行为数量控制
   - 最多返回2个行为
   - 避免过度干预
```

**输出：Decision**
```python
class Decision(BaseModel):
    province_id: int
    decision_type: DecisionType  # 'execute_instruction' | 'autonomous_action' | 'no_action'
    behaviors: List[BehaviorDefinition]
    reasoning: str
    risk_assessment: RiskAssessment
    expected_outcomes: List[str]

class BehaviorDefinition(BaseModel):
    behavior_type: BehaviorType  # 'tax_adjustment' | 'spending_change' | ...
    parameters: Dict[str, float]  # Agent决定的具体参数
    duration: Optional[int]  # 持续时间（月）
    priority: int  # 优先级
    reasoning: str  # 行为理由

class BehaviorType(str, Enum):
    TAX_ADJUSTMENT = "tax_adjustment"
    SPENDING_CHANGE = "spending_change"
    INFRASTRUCTURE_INVESTMENT = "infrastructure_investment"
    STABILITY_IMPROVEMENT = "stability_improvement"
    LOYALTY_BUILDING = "loyalty_building"

class RiskAssessment(BaseModel):
    overall_risk: str  # 'low' | 'medium' | 'high'
    loyalty_risk: float
    stability_risk: float
    financial_risk: float
    recommendations: List[str]
```

**行为模板系统：**

预定义行为类型和参数范围，Agent在范围内选择具体值：

```python
behavior_templates = {
    'raise_tax': {
        'behavior_type': BehaviorType.TAX_ADJUSTMENT,
        'parameter_ranges': {
            'rate_change': (0.01, 0.20),  # 1%-20%
            'duration': (3, 12)
        },
        'default_duration': 6,
        'preconditions': {
            'min_loyalty': 50,  # 忠诚度要求
            'min_stability': 50
        },
        'effects': {
            'income_multiplier': '1 + rate_change',
            'loyalty_change': '-rate_change * 50',
            'stability_change': '-rate_change * 30'
        }
    },

    'reduce_tax': {
        'behavior_type': BehaviorType.TAX_ADJUSTMENT,
        'parameter_ranges': {
            'rate_change': (-0.15, -0.01),  # -15%到-1%
            'duration': (3, 12)
        },
        'default_duration': 6,
        'effects': {
            'income_multiplier': '1 + rate_change',
            'loyalty_change': '-rate_change * 50',  # 负负得正
            'stability_change': '-rate_change * 30'
        }
    },

    'invest_infrastructure': {
        'behavior_type': BehaviorType.INFRASTRUCTURE_INVESTMENT,
        'parameter_ranges': {
            'amount': (50, 500),  # 投资金额
            'duration': (6, 24)   # 建设周期
        },
        'default_duration': 12,
        'preconditions': {
            'min_treasury': 100  # 最低国库要求
        },
        'effects': {
            'expenditure_increase': 'amount',
            'development_bonus': 'amount / 100',
            'loyalty_change': 5,
            'stability_change': 3
        }
    },

    'reduce_spending': {
        'behavior_type': BehaviorType.SPENDIND_CHANGE,
        'parameter_ranges': {
            'ratio_change': (-0.30, -0.05),  # 减少5%-30%
            'duration': (3, 12)
        },
        'default_duration': 6,
        'effects': {
            'expenditure_multiplier': '1 + ratio_change',
            'loyalty_change': '-ratio_change * 20',  # 负负得正
            'stability_change': '-ratio_change * 10'
        }
    },

    'increase_spending': {
        'behavior_type': BehaviorType.SPENDIND_CHANGE,
        'parameter_ranges': {
            'ratio_change': (0.05, 0.30),  # 增加5%-30%
            'duration': (3, 12)
        },
        'default_duration': 6,
        'effects': {
            'expenditure_multiplier': '1 + ratio_change',
            'loyalty_change': 10,
            'stability_change': 5
        }
    },

    'stability_improvement': {
        'behavior_type': BehaviorType.STABILITY_IMPROVEMENT,
        'parameter_ranges': {
            'policy_type': ['security_enhancement', 'law_enforcement', 'corruption_crackdown'],
            'duration': (4, 8)
        },
        'default_duration': 6,
        'effects': {
            'stability_change': 10,
            'expenditure_increase': 50,
            'loyalty_change': 2
        }
    },

    'loyalty_building': {
        'behavior_type': BehaviorType.LOYALTY_BUILDING,
        'parameter_ranges': {
            'action_type': ['tax_relief', 'public_works', 'celebration'],
            'amount': (50, 200)
        },
        'default_duration': 3,
        'effects': {
            'loyalty_change': 15,
            'expenditure_increase': 'amount',
            'income_decrease': '-amount * 0.5'
        }
    }
}
```

**关键方法实现：**

1. `_evaluate_instruction()`
   - 获取指令模板
   - 检查前置条件（忠诚度、国库、稳定性）
   - 判断是否在合理范围
   - 返回InstructionEvaluation（可行/不可行 + 建议）

2. `_create_behaviors_for_instruction()`
   - 使用指令模板
   - Agent决定参数（在预定义范围内）
   - 可选：使用LLM生成参数
   - 创建主要行为
   - 调用_create_auxiliary_behaviors()添加辅助行为

3. `_select_autonomous_behaviors()`
   - 分析perception.trends
   - 根据规则选择行为：
     - income_trend == 'decreasing' → 税收调整或支出削减
     - loyalty < 60 → 忠诚度建设
     - stability < 60 → 稳定性提升
     - 都正常 → 基础设施投资
   - 返回1-2个行为

4. `_validate_behavior()`
   - 检查行为类型是否存在
   - 检查参数是否在范围内
   - 返回ValidationResult

5. `_assess_risks()`
   - 计算每个行为的风险
   - 累加忠诚度风险、稳定性风险、财务风险
   - 判断总体风险级别
   - 生成建议

6. `_decide_behavior_parameters()`
   - 从behavior_templates获取参数范围
   - Agent在范围内选择值
   - 可选：使用LLM基于历史数据优化参数
   - 返回参数字典

#### 2.3.3 ExecutionAgent（执行Agent）

**职责：**
1. 接收Decision（包含BehaviorDefinition列表）
2. 执行每个行为
3. 计算行为效果
4. 修改Province属性
5. 生成事件
6. 生成月度报告
7. 记录行为历史

**输入：**
- decision: Decision
- province: Province
- month: int
- year: int

**执行流程：**
```
1. 遍历decision.behaviors

2. 对每个behavior：
   a. 参数验证（再次确认）
   b. 调用对应的_execute方法
   c. 计算效果（返回effects字典）
   d. 修改Province属性
   e. 生成事件（通过AgentEventGenerator）
   f. 保存到province_behaviors表
   g. 记录执行结果（成功/失败）

3. 汇总所有执行结果

4. 生成月度报告
   - 统计成功/失败行为
   - 汇总总效果
   - 生成报告摘要

5. 返回ExecutionResult
```

**输出：ExecutionResult**
```python
class ExecutionResult(BaseModel):
    province_id: int
    month: int
    year: int
    executed_behaviors: List[ExecutedBehavior]
    monthly_report: MonthlyReport
    generated_events: List[Event]
    execution_summary: str

class ExecutedBehavior(BaseModel):
    behavior_id: int
    behavior_definition: BehaviorDefinition
    effects: Dict[str, float]
    success: bool
    execution_summary: str

class MonthlyReport(BaseModel):
    month: int
    year: int
    province_id: int
    province_name: str
    executed_behaviors_count: int
    failed_behaviors_count: int
    total_effects: Dict[str, float]
    summary: str
```

**行为效果计算：**

每个行为类型都有对应的_execute方法，计算具体效果：

```python
async def _apply_tax_adjustment(params, province):
    """
    应用税收调整

    参数：
      - rate_change: 税率变化（-0.15到+0.20）
      - duration: 持续时间（3-12个月）

    效果：
      - income_multiplier: 收入倍数（1 + rate_change）
      - loyalty_change: 忠诚度变化（-rate_change * 50）
      - stability_change: 稳定性变化（-rate_change * 30）
    """
    rate_change = params.get('rate_change', 0.0)

    return {
        'income_multiplier': 1.0 + rate_change,
        'loyalty_change': -rate_change * 50,
        'stability_change': -rate_change * 30
    }

async def _apply_spending_change(params, province):
    """
    应用支出调整

    参数：
      - ratio_change: 支出比例变化（-0.30到+0.30）
      - category: 支出类别（'all', 'military', 'admin'等）

    效果：
      - expenditure_multiplier: 支出倍数（1 + ratio_change）
      - loyalty_change: 忠诚度变化
      - stability_change: 稳定性变化
    """
    ratio_change = params.get('ratio_change', 0.0)
    category = params.get('category', 'all')

    loyalty_change = 0.0
    stability_change = 0.0

    # 削减支出会降低忠诚度和稳定性
    if ratio_change < 0:
        loyalty_change = -ratio_change * 20  # 负负得正，但仍有负面效果
        stability_change = -ratio_change * 10

    return {
        'expenditure_multiplier': 1.0 + ratio_change,
        'loyalty_change': loyalty_change,
        'stability_change': stability_change
    }

async def _apply_infrastructure_investment(params, province):
    """
    应用基础设施投资

    参数：
      - amount: 投资金额（50-500）
      - duration: 建设周期（6-24个月）

    效果：
      - expenditure_increase: 支出增加（amount）
      - development_bonus: 发展度提升（amount / 100）
      - loyalty_change: 忠诚度提升（+5）
      - stability_change: 稳定性提升（+3）
    """
    investment_type = params.get('investment_type', 'road_improvement')
    amount = params.get('amount', 100)

    # 不同投资类型有不同的加成
    type_bonus = {
        'road_improvement': 1.0,
        'irrigation': 1.2,  # 农业加成
        'fortification': 0.8,  # 军事加成
        'market': 1.5  # 商业加成
    }

    bonus = type_bonus.get(investment_type, 1.0)

    return {
        'expenditure_increase': amount,
        'development_bonus': (amount / 100) * bonus,
        'loyalty_change': 5,
        'stability_change': 3
    }

async def _apply_stability_improvement(params, province):
    """
    应用稳定性提升

    参数：
      - policy_type: 政策类型
      - duration: 持续时间（4-8个月）

    效果：
      - stability_change: 稳定性提升（+10）
      - expenditure_increase: 支出增加（50）
      - loyalty_change: 忠诚度变化（+2）
    """
    policy_type = params.get('policy_type', 'security_enhancement')

    # 不同政策类型有不同效果
    policy_effects = {
        'security_enhancement': {'stability': 10, 'cost': 50},
        'law_enforcement': {'stability': 8, 'cost': 40},
        'corruption_crackdown': {'stability': 12, 'loyalty': 5, 'cost': 60}
    }

    effects = policy_effects.get(policy_type, {'stability': 10, 'cost': 50})

    return {
        'stability_change': effects['stability'],
        'expenditure_increase': effects['cost'],
        'loyalty_change': effects.get('loyalty', 2)
    }

async def _apply_loyalty_building(params, province):
    """
    应用忠诚度建设

    参数：
      - action_type: 行动类型
      - amount: 金额（50-200）

    效果：
      - loyalty_change: 忠诚度提升（+15）
      - expenditure_increase: 支出增加（amount）
      - income_decrease: 收入减少（-amount * 0.5）
    """
    action_type = params.get('action_type', 'tax_relief')
    amount = params.get('amount', 50)

    # 不同行动类型有不同效果
    action_effects = {
        'tax_relief': {'loyalty': 15, 'income_loss': 0.5},
        'public_works': {'loyalty': 12, 'income_loss': 0.3},
        'celebration': {'loyalty': 10, 'income_loss': 0.2}
    }

    effects = action_effects.get(action_type, {'loyalty': 15, 'income_loss': 0.5})

    return {
        'loyalty_change': effects['loyalty'],
        'expenditure_increase': amount,
        'income_decrease': -amount * effects['income_loss']
    }
```

**事件生成：**

ExecutionAgent通过AgentEventGenerator为每个行为生成事件：

```python
async def _generate_behavior_event(behavior, effect, province, month, year):
    """
    为行为生成事件

    流程：
      1. 映射行为类型到事件类型
      2. 调用AgentEventGenerator创建事件
      3. 自定义事件描述（narrative）
      4. 添加事件效果（EventEffect）
      5. 返回Event对象
    """
    # 1. 映射行为类型到事件类型
    event_type_map = {
        BehaviorType.TAX_ADJUSTMENT: AgentEventType.TAX_ADJUSTMENT,
        BehaviorType.SPENDIND_CHANGE: AgentEventType.BUDGET_REALLOCATION,
        BehaviorType.INFRASTRUCTURE_INVESTMENT: AgentEventType.INFRASTRUCTURE_PROJECT,
        BehaviorType.STABILITY_IMPROVEMENT: AgentEventType.POLITICAL_REFORM,
        BehaviorType.LOYALTY_BUILDING: AgentEventType.POLITICAL_REFORM
    }

    agent_event_type = event_type_map.get(behavior.behavior_type)
    if not agent_event_type:
        return None

    # 2. 创建事件（使用AgentEventGenerator）
    event = self.agent_event_generator.create_event_from_type(
        event_type=agent_event_type,
        governor=self,
        province_id=province.province_id,
        month=month
    )

    # 3. 自定义事件描述
    event.narrative = self._build_event_narrative(behavior, effect, province)
    event.description = event.narrative

    # 4. 添加事件效果
    event.instant_effects = []
    event.continuous_effects = []

    # 将behavior效果转换为EventEffect
    for key, value in effect.items():
        effect_scope = self._map_effect_key_to_scope(key)
        if effect_scope:
            event_effect = EventEffect(
                scope=effect_scope,
                operation=EffectOperation.ADD,
                value=value
            )
            event.continuous_effects.append(event_effect)

    return event
```

**关键方法实现：**

1. `execute()`
   - 主入口方法
   - 遍历所有behavior
   - 调用_execute_behavior()
   - 生成事件
   - 生成报告
   - 返回ExecutionResult

2. `_execute_behavior()`
   - 根据behavior_type路由到对应的_apply方法
   - 返回effects字典
   - 捕获异常，标记失败

3. `_generate_behavior_event()`
   - 映射行为类型到事件类型
   - 使用AgentEventGenerator创建事件
   - 自定义事件描述
   - 添加事件效果

4. `_save_behavior_to_db()`
   - 保存到province_behaviors表
   - 记录behavior类型、参数、效果、reasoning
   - 返回behavior_id

5. `_generate_monthly_report()`
   - 统计成功/失败行为
   - 汇总总效果
   - 生成报告摘要
   - 返回MonthlyReport

### 2.4 数据库设计

#### 2.4.1 表结构详细设计

**表1：province_monthly_summaries（月度摘要）**
```sql
CREATE TABLE province_monthly_summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 标识字段
    province_id INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,

    -- 基础属性
    population INTEGER,
    development_level REAL,
    loyalty REAL,
    stability REAL,

    -- 财务数据
    actual_income REAL,
    actual_expenditure REAL,
    reported_income REAL,
    reported_expenditure REAL,
    actual_surplus REAL,
    reported_surplus REAL,

    -- 趋势标记（简化存储）
    income_trend TEXT,              -- 'increasing' | 'stable' | 'decreasing'
    expenditure_trend TEXT,
    loyalty_trend TEXT,

    -- 事件摘要（JSON格式）
    major_events TEXT,              -- [{"event_type": "...", "severity": 0.5}]
    event_count INTEGER DEFAULT 0,

    -- Agent决策摘要（JSON格式）
    agent_decision TEXT,            -- {"action_type": "...", "params": {...}}

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (province_id) REFERENCES provinces(province_id),

    -- 唯一约束
    UNIQUE(province_id, month, year)
);

-- 索引
CREATE INDEX idx_monthly_summaries_province_month
    ON province_monthly_summaries(province_id, month, year);
```

**数据示例：**
```json
{
  "summary_id": 1,
  "province_id": 1,
  "month": 12,
  "year": 1,
  "population": 35000,
  "development_level": 7.5,
  "loyalty": 75.0,
  "stability": 72.0,
  "actual_income": 850.0,
  "actual_expenditure": 600.0,
  "reported_income": 850.0,
  "reported_expenditure": 600.0,
  "actual_surplus": 250.0,
  "reported_surplus": 250.0,
  "income_trend": "increasing",
  "expenditure_trend": "stable",
  "loyalty_trend": "stable",
  "major_events": "[{\"event_type\": \"harvest_festival\", \"severity\": 0.3}]",
  "event_count": 1,
  "agent_decision": "{\"action_type\": \"tax_adjustment\", \"params\": {\"rate_change\": 0.05}}"
}
```

**表2：province_quarterly_summaries（季度摘要）**
```sql
CREATE TABLE province_quarterly_summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 标识字段
    province_id INTEGER NOT NULL,
    quarter INTEGER NOT NULL,        -- 1-4
    year INTEGER NOT NULL,

    -- 统计指标（基于月度数据聚合）
    avg_income REAL,
    median_income REAL,
    avg_expenditure REAL,
    median_expenditure REAL,
    total_surplus REAL,

    -- 趋势分析
    income_trend TEXT,              -- 对比上个季度
    expenditure_trend TEXT,
    loyalty_change REAL,            -- 季度内变化
    stability_change REAL,

    -- 关键事件索引（JSON格式）
    major_events TEXT,              -- [{"event": "...", "month": 2}]
    special_event_types TEXT,       -- ["rebellion", "disaster"]

    -- 关键决策摘要（JSON格式）
    key_decisions TEXT,             -- [{"action": "...", "result": "..."}]

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (province_id) REFERENCES provinces(province_id),

    -- 唯一约束
    UNIQUE(province_id, quarter, year)
);

-- 索引
CREATE INDEX idx_quarterly_summaries_province_quarter
    ON province_quarterly_summaries(province_id, quarter, year);
```

**数据示例：**
```json
{
  "summary_id": 1,
  "province_id": 1,
  "quarter": 4,
  "year": 1,
  "avg_income": 850.0,
  "median_income": 845.0,
  "avg_expenditure": 600.0,
  "median_expenditure": 595.0,
  "total_surplus": 750.0,
  "income_trend": "increasing",
  "expenditure_trend": "stable",
  "loyalty_change": 2.5,
  "stability_change": -1.0,
  "major_events": "[{\"event\": \"harvest_festival\", \"month\": 10}]",
  "special_event_types": "[]",
  "key_decisions": "[{\"action\": \"tax_adjustment\", \"result\": \"success\"}]"
}
```

**表3：province_annual_summaries（年度摘要）**
```sql
CREATE TABLE province_annual_summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 标识字段
    province_id INTEGER NOT NULL,
    year INTEGER NOT NULL,

    -- 年度统计
    total_income REAL,
    total_expenditure REAL,
    avg_monthly_income REAL,
    avg_monthly_expenditure REAL,
    total_surplus REAL,

    -- 年度变化
    population_change INTEGER,      -- 净变化
    development_change REAL,
    loyalty_start REAL,
    loyalty_end REAL,
    loyalty_change REAL,

    -- 重大事件索引（只记录特殊事件）
    major_events TEXT,              -- JSON array
    disaster_count INTEGER DEFAULT 0,
    rebellion_count INTEGER DEFAULT 0,

    -- 年度评价
    performance_rating TEXT,        -- 'excellent' | 'good' | 'average' | 'poor'

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (province_id) REFERENCES provinces(province_id),

    -- 唯一约束
    UNIQUE(province_id, year)
);

-- 索引
CREATE INDEX idx_annual_summaries_province_year
    ON province_annual_summaries(province_id, year);
```

**数据示例：**
```json
{
  "summary_id": 1,
  "province_id": 1,
  "year": 1,
  "total_income": 10200.0,
  "total_expenditure": 7200.0,
  "avg_monthly_income": 850.0,
  "avg_monthly_expenditure": 600.0,
  "total_surplus": 3000.0,
  "population_change": 500,
  "development_change": 0.5,
  "loyalty_start": 72.5,
  "loyalty_end": 75.0,
  "loyalty_change": 2.5,
  "major_events": "[]",
  "disaster_count": 0,
  "rebellion_count": 0,
  "performance_rating": "good"
}
```

**表4：player_instructions（玩家指令）**
```sql
CREATE TABLE player_instructions (
    instruction_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 关联省份（可选，None表示全国性指令）
    province_id INTEGER,

    -- 时间标识
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,

    -- 指令内容
    instruction_type TEXT NOT NULL,  -- 'raise_tax' | 'invest_infrastructure' | ...
    template_name TEXT NOT NULL,     -- 预定义模板名称

    -- 指令参数（由Agent填充）
    parameters TEXT,                 -- JSON: {"tax_rate": 0.15, "duration": 6}

    -- 执行状态
    status TEXT DEFAULT 'pending',   -- 'pending' | 'executing' | 'completed' | 'failed'
    execution_month INTEGER,         -- 实际执行的月份

    -- 执行结果
    result_summary TEXT,             -- JSON: {"actual_tax_increase": 0.05}
    agent_reasoning TEXT,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (province_id) REFERENCES provinces(province_id)
);

-- 索引
CREATE INDEX idx_instructions_status
    ON player_instructions(status, month, year);

CREATE INDEX idx_instructions_province
    ON player_instructions(province_id, month, year);
```

**数据示例：**
```json
{
  "instruction_id": 1,
  "province_id": 1,
  "month": 12,
  "year": 1,
  "instruction_type": "raise_tax",
  "template_name": "raise_tax",
  "parameters": "{\"rate_change\": 0.08, \"duration\": 6}",
  "status": "completed",
  "execution_month": 12,
  "result_summary": "{\"actual_tax_increase\": 0.08, \"income_increase\": 68.0, \"loyalty_decrease\": -4.0}",
  "agent_reasoning": "Executing player instruction to raise tax by 8% over 6 months"
}
```

**表5：province_behaviors（Agent行为记录）**
```sql
CREATE TABLE province_behaviors (
    behavior_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 标识字段
    province_id INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,

    -- 行为定义
    behavior_type TEXT NOT NULL,     -- 'tax_adjustment' | 'spending_change' | ...
    behavior_name TEXT NOT NULL,

    -- 行为参数（JSON格式）
    parameters TEXT,

    -- 行为效果（JSON格式）
    effects TEXT,                    -- {"income_change": +50, "loyalty_change": -5}

    -- 是否响应玩家指令
    in_response_to_instruction INTEGER,  -- player_instructions.instruction_id

    -- Agent的决策理由
    reasoning TEXT,

    -- 行为验证
    is_valid BOOLEAN DEFAULT 1,
    validation_error TEXT,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (province_id) REFERENCES provinces(province_id),
    FOREIGN KEY (in_response_to_instruction) REFERENCES player_instructions(instruction_id)
);

-- 索引
CREATE INDEX idx_behaviors_province_month
    ON province_behaviors(province_id, month, year);

CREATE INDEX idx_behaviors_instruction
    ON province_behaviors(in_response_to_instruction);
```

**数据示例：**
```json
{
  "behavior_id": 1,
  "province_id": 1,
  "month": 12,
  "year": 1,
  "behavior_type": "tax_adjustment",
  "behavior_name": "tax_adjustment",
  "parameters": "{\"rate_change\": 0.08, \"duration\": 6}",
  "effects": "{\"income_multiplier\": 1.08, \"loyalty_change\": -4.0, \"stability_change\": -2.4}",
  "in_response_to_instruction": 1,
  "reasoning": "Executing player instruction to raise tax by 8%",
  "is_valid": true,
  "validation_error": null
}
```

**表6：special_events_index（特殊事件索引）**
```sql
CREATE TABLE special_events_index (
    index_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 关联事件
    event_id TEXT NOT NULL,
    province_id INTEGER NOT NULL,

    -- 事件分类
    event_category TEXT NOT NULL,    -- 'rebellion' | 'war' | 'disaster' | 'crisis'

    -- 时间标识
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,

    -- 事件摘要
    event_name TEXT,
    severity REAL,
    impact_description TEXT,

    -- 事件关联
    related_behaviors TEXT,          -- JSON: [behavior_id, ...]

    -- 快速检索标记
    is_resolved BOOLEAN DEFAULT 0,

    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- 外键约束
    FOREIGN KEY (province_id) REFERENCES provinces(province_id),
    FOREIGN KEY (event_id) REFERENCES events(event_id)
);

-- 索引
CREATE INDEX idx_special_events_province
    ON special_events_index(province_id, event_category, month);

CREATE INDEX idx_special_events_category
    ON special_events_index(event_category, is_resolved);
```

**数据示例：**
```json
{
  "index_id": 1,
  "event_id": "evt_123",
  "province_id": 1,
  "event_category": "rebellion",
  "month": 6,
  "year": 1,
  "event_name": "Peasant Uprising",
  "severity": 0.8,
  "impact_description": "Large-scale rebellion in northern territory",
  "related_behaviors": "[15, 16]",
  "is_resolved": true
}
```

#### 2.4.2 数据库迁移脚本

```python
# /db/migrations/add_province_agent_tables.py

import sqlite3
from typing import List

class Migration:
    """数据库迁移：添加Province Agent相关表"""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def up(self) -> None:
        """执行迁移"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 创建province_monthly_summaries表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS province_monthly_summaries (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    province_id INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    population INTEGER,
                    development_level REAL,
                    loyalty REAL,
                    stability REAL,
                    actual_income REAL,
                    actual_expenditure REAL,
                    reported_income REAL,
                    reported_expenditure REAL,
                    actual_surplus REAL,
                    reported_surplus REAL,
                    income_trend TEXT,
                    expenditure_trend TEXT,
                    loyalty_trend TEXT,
                    major_events TEXT,
                    event_count INTEGER DEFAULT 0,
                    agent_decision TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                    UNIQUE(province_id, month, year)
                )
            """)

            # 创建province_quarterly_summaries表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS province_quarterly_summaries (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    province_id INTEGER NOT NULL,
                    quarter INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    avg_income REAL,
                    median_income REAL,
                    avg_expenditure REAL,
                    median_expenditure REAL,
                    total_surplus REAL,
                    income_trend TEXT,
                    expenditure_trend TEXT,
                    loyalty_change REAL,
                    stability_change REAL,
                    major_events TEXT,
                    special_event_types TEXT,
                    key_decisions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                    UNIQUE(province_id, quarter, year)
                )
            """)

            # 创建province_annual_summaries表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS province_annual_summaries (
                    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    province_id INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    total_income REAL,
                    total_expenditure REAL,
                    avg_monthly_income REAL,
                    avg_monthly_expenditure REAL,
                    total_surplus REAL,
                    population_change INTEGER,
                    development_change REAL,
                    loyalty_start REAL,
                    loyalty_end REAL,
                    loyalty_change REAL,
                    major_events TEXT,
                    disaster_count INTEGER DEFAULT 0,
                    rebellion_count INTEGER DEFAULT 0,
                    performance_rating TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                    UNIQUE(province_id, year)
                )
            """)

            # 创建player_instructions表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_instructions (
                    instruction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    province_id INTEGER,
                    month INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    instruction_type TEXT NOT NULL,
                    template_name TEXT NOT NULL,
                    parameters TEXT,
                    status TEXT DEFAULT 'pending',
                    execution_month INTEGER,
                    result_summary TEXT,
                    agent_reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (province_id) REFERENCES provinces(province_id)
                )
            """)

            # 创建province_behaviors表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS province_behaviors (
                    behavior_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    province_id INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    behavior_type TEXT NOT NULL,
                    behavior_name TEXT NOT NULL,
                    parameters TEXT,
                    effects TEXT,
                    in_response_to_instruction INTEGER,
                    reasoning TEXT,
                    is_valid BOOLEAN DEFAULT 1,
                    validation_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                    FOREIGN KEY (in_response_to_instruction) REFERENCES player_instructions(instruction_id)
                )
            """)

            # 创建special_events_index表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS special_events_index (
                    index_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL,
                    province_id INTEGER NOT NULL,
                    event_category TEXT NOT NULL,
                    month INTEGER NOT NULL,
                    year INTEGER NOT NULL,
                    event_name TEXT,
                    severity REAL,
                    impact_description TEXT,
                    related_behaviors TEXT,
                    is_resolved BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (province_id) REFERENCES provinces(province_id),
                    FOREIGN KEY (event_id) REFERENCES events(event_id)
                )
            """)

            # 修改monthly_reports表
            try:
                cursor.execute("ALTER TABLE monthly_reports ADD COLUMN agent_behavior_id INTEGER")
            except sqlite3.OperationalError:
                pass  # 列已存在

            try:
                cursor.execute("ALTER TABLE monthly_reports ADD COLUMN player_instruction_id INTEGER")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE monthly_reports ADD COLUMN decision_summary TEXT")
            except sqlite3.OperationalError:
                pass

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_monthly_summaries_province_month
                ON province_monthly_summaries(province_id, month, year)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_quarterly_summaries_province_quarter
                ON province_quarterly_summaries(province_id, quarter, year)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_annual_summaries_province_year
                ON province_annual_summaries(province_id, year)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_behaviors_province_month
                ON province_behaviors(province_id, month, year)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_instructions_status
                ON player_instructions(status, month, year)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_special_events_province
                ON special_events_index(province_id, event_category, month)
            """)

            conn.commit()
            print("Migration completed successfully")

        except Exception as e:
            conn.rollback()
            print(f"Migration failed: {e}")
            raise
        finally:
            conn.close()

    def down(self) -> None:
        """回滚迁移"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # 删除表（注意顺序：先删除有外键的表）
            cursor.execute("DROP TABLE IF EXISTS special_events_index")
            cursor.execute("DROP TABLE IF EXISTS province_behaviors")
            cursor.execute("DROP TABLE IF EXISTS player_instructions")
            cursor.execute("DROP TABLE IF EXISTS province_annual_summaries")
            cursor.execute("DROP TABLE IF EXISTS province_quarterly_summaries")
            cursor.execute("DROP TABLE IF EXISTS province_monthly_summaries")

            conn.commit()
            print("Rollback completed successfully")

        except Exception as e:
            conn.rollback()
            print(f"Rollback failed: {e}")
            raise
        finally:
            conn.close()
```

---

## 三、实现方法

### 3.1 实现阶段划分

#### Phase 1: 核心基础设施（Week 1-2）

**目标：** 建立数据层和基础Agent框架

**任务列表：**

1. **数据库迁移（2天）**
   - 创建6个新表
   - 修改monthly_reports表
   - 编写迁移脚本
   - 创建索引优化查询
   - 测试迁移和回滚

2. **Database扩展（1天）**
   - 实现新的CRUD方法：
     - `save_monthly_summary()`
     - `get_monthly_summaries()`
     - `save_quarterly_summary()`
     - `get_quarterly_summaries()`
     - `save_annual_summary()`
     - `get_annual_summaries()`
     - `save_player_instruction()`
     - `get_pending_instructions()`
     - `save_province_behavior()`
     - `get_province_behaviors()`
     - `index_special_event()`
     - `get_special_events()`
   - 单元测试

3. **PerceptionAgent实现（3天）**
   - 创建文件：`/agents/province/perception_agent.py`
   - 实现基础框架（继承BaseAgent）
   - 实现`perceive()`主方法
   - 实现`_build_monthly_detailed()`
   - 实现`_build_quarterly_summaries()`
   - 实现`_build_annual_summaries()`
   - 实现`_index_critical_events()`
   - 实现`_analyze_trends()`
   - 单元测试

**验收标准：**
- 数据库表创建成功，索引有效
- Database方法测试通过
- PerceptionAgent能够读取历史数据并生成PerceptionContext
- 单元测试覆盖率 > 80%

#### Phase 2: 决策系统（Week 3-4）

**目标：** 实现决策逻辑和指令处理

**任务列表：**

1. **数据模型定义（1天）**
   - 创建文件：`/agents/province/models.py`
   - 定义`PerceptionContext`
   - 定义`Decision`
   - 定义`BehaviorDefinition`
   - 定义`ExecutionResult`
   - 定义`PlayerInstruction`

2. **行为定义系统（2天）**
   - 创建文件：`/agents/province/behaviors.py`
   - 定义`BehaviorType`枚举
   - 实现行为模板库（`behavior_templates`字典）
   - 定义每个行为的参数范围
   - 定义每个行为的效果公式
   - 实现参数验证逻辑
   - 单元测试

3. **DecisionAgent实现（4天）**
   - 创建文件：`/agents/province/decision_agent.py`
   - 实现基础框架（继承BaseAgent）
   - 实现`make_decision()`主方法
   - 实现`_evaluate_instruction()`
   - 实现`_create_behaviors_for_instruction()`
   - 实现`_select_autonomous_behaviors()`
   - 实现`_validate_behavior()`
   - 实现`_assess_risks()`
   - 实现`_decide_behavior_parameters()`
   - 单元测试

4. **PlayerInstruction系统（2天）**
   - 扩展`models.py`，添加指令相关模型
   - 定义指令模板（与行为模板对应）
   - CLI接口（玩家输入指令）
   - 指令状态管理
   - 单元测试

**验收标准：**
- DecisionAgent能够评估指令并做出决策
- 行为参数验证逻辑正确
- 风险评估合理
- 玩家可以通过CLI下达指令
- 单元测试覆盖率 > 80%

#### Phase 3: 执行系统（Week 5-6）

**目标：** 实现行为执行和报告生成

**任务列表：**

1. **ExecutionAgent实现（4天）**
   - 创建文件：`/agents/province/execution_agent.py`
   - 实现基础框架（继承BaseAgent）
   - 实现`execute()`主方法
   - 实现`_execute_behavior()`
   - 实现`_apply_tax_adjustment()`
   - 实现`_apply_spending_change()`
   - 实现`_apply_infrastructure_investment()`
   - 实现`_apply_stability_improvement()`
   - 实现`_apply_loyalty_building()`
   - 单元测试

2. **事件生成集成（2天）**
   - 实现`_generate_behavior_event()`
   - 实现`_build_event_narrative()`
   - 扩展AgentEventGenerator支持behavior→event映射
   - 实现效果转换（behavior effects → EventEffect）
   - 集成测试

3. **报告生成系统（2天）**
   - 实现`_generate_monthly_report()`
   - 实现`_build_report_summary()`
   - 实现`_save_behavior_to_db()`
   - 与monthly_reports表集成
   - 单元测试

**验收标准：**
- ExecutionAgent能够执行所有预定义行为
- 行为效果计算正确
- 事件生成成功
- 月度报告格式正确
- 行为记录保存到数据库
- 单元测试覆盖率 > 80%

#### Phase 3.5: 串行依赖实现（Week 6.5-7）

**目标：** 确保感知-决策-执行的严格串行顺序

**背景：** 三个Agent之间存在严格的依赖关系，必须按顺序执行，不可并行

**任务列表：**

1. **串行执行框架（2天）**
   - 创建：`/core/province_agent_orchestrator.py`
   - 实现`ProvinceAgentOrchestrator`类
   - 定义串行执行接口：`perceive() → decide() → execute()`
   - 实现错误处理和回退机制
   - 确保数据在阶段间正确传递

2. **依赖管理（1天）**
   - 实现阶段间数据传递验证
   - 添加超时机制（每个阶段最大执行时间）
   - 实现失败重试逻辑
   - 确保PerceptionContext → Decision → ExecutionResult的传递

3. **与Game Loop集成（1天）**
   - 修改`Game.next_month()`支持串行调用
   - 确保在GovernorAgent之前完成新Agent流程
   - 实现临时数据存储（_current_perceptions等）
   - 验证数据一致性

**验收标准：**
- 三个Agent必须严格按顺序执行
- 前一阶段失败时后续阶段不能执行
- 数据传递正确无误
- 性能开销可接受（总延迟 < 2秒）

#### Phase 4: 集成和测试（Week 7-8）

**目标：** 与现有系统集成，端到端测试

**任务列表：**

1. **Game.next_month()集成（3天）**
   - 修改`/core/game.py`
   - 在游戏主循环中插入3个Agent调用
   - 与GovernorAgent协调
   - 与Event系统集成
   - 调试数据流

2. **CLI界面（2天）**
   - 创建文件：`/ui/province_agent_cli.py`
   - 玩家指令输入界面
   - Agent决策显示
   - 行为执行反馈
   - 历史摘要查看
   - 集成到main.py

3. **端到端测试（3天）**
   - 完整流程测试
   - 边界条件测试
   - 性能测试
   - 修复bug

**验收标准：**
- 完整流程可以跑通
- 边界条件处理正确
- 性能满足要求（查询 < 100ms，决策 < 500ms）
- 无严重bug

#### Phase 5: 增强功能（Week 9-10）

**目标：** LLM集成和高级特性

**任务列表：**

1. **LLM增强（4天）**
   - PerceptionAgent使用LLM分析趋势
   - DecisionAgent使用LLM优化决策参数
   - ExecutionAgent使用LLM生成事件描述
   - 性能优化（缓存、批处理）

2. **高级特性（可选，5天）**
   - 自适应学习（记住哪些行为有效）
   - 风险预测模型
   - 多目标优化

**验收标准：**
- LLM增强功能可选开关
- 性能可接受（LLM调用 < 2s）
- 高级特性通过测试

### 3.2 测试策略

#### 3.2.1 单元测试

**PerceptionAgent测试：**
```python
# tests/test_perception_agent.py

def test_build_monthly_detailed():
    """测试月度详细数据构建"""
    # 准备测试数据
    # 调用_perceive()
    # 验证返回的PerceptionContext
    pass

def test_build_quarterly_summaries():
    """测试季度摘要生成"""
    # 准备测试数据（3个月的月度数据）
    # 调用_build_quarterly_summaries()
    # 验证统计指标正确
    pass

def test_analyze_trends():
    """测试趋势分析"""
    # 准备测试数据（收入递增的季度）
    # 调用_analyze_trends()
    # 验证trend == 'increasing'
    pass

def test_index_critical_events():
    """测试关键事件索引"""
    # 准备测试数据（包含叛乱事件）
    # 调用_index_critical_events()
    # 验证返回叛乱事件
    pass
```

**DecisionAgent测试：**
```python
# tests/test_decision_agent.py

def test_evaluate_instruction_feasible():
    """测试指令评估 - 可行"""
    # 准备测试数据（忠诚度80，稳定性80）
    # 创建raise_tax指令
    # 调用_evaluate_instruction()
    # 验证is_feasible == True
    pass

def test_evaluate_instruction_not_feasible():
    """测试指令评估 - 不可行"""
    # 准备测试数据（忠诚度30）
    # 创建raise_tax指令
    # 调用_evaluate_instruction()
    # 验证is_feasible == False
    # 验证有建议修改
    pass

def test_select_autonomous_behaviors():
    """测试自主行为选择"""
    # 准备测试数据（忠诚度低）
    # 调用_select_autonomous_behaviors()
    # 验证返回loyalty_building行为
    pass

def test_validate_behavior():
    """测试参数验证"""
    # 准备测试数据（参数超出范围）
    # 调用_validate_behavior()
    # 验证返回is_valid == False
    pass
```

**ExecutionAgent测试：**
```python
# tests/test_execution_agent.py

def test_execute_tax_adjustment():
    """测试税收调整执行"""
    # 准备测试数据
    # 创建tax_adjustment行为
    # 调用_execute()
    # 验证效果正确（income_multiplier == 1.05）
    pass

def test_generate_behavior_event():
    """测试事件生成"""
    # 准备测试数据
    # 创建behavior和effect
    # 调用_generate_behavior_event()
    # 验证返回Event对象
    # 验证事件描述正确
    pass

def test_save_behavior_to_db():
    """测试行为保存"""
    # 准备测试数据
    # 调用_save_behavior_to_db()
    # 验证数据库中存在记录
    pass
```

#### 3.2.2 集成测试

```python
# tests/test_province_agent_integration.py

def test_full_workflow_with_instruction():
    """测试完整流程 - 有玩家指令"""
    # 1. 初始化游戏
    # 2. 玩家下达raise_tax指令
    # 3. 调用PerceptionAgent.perceive()
    # 4. 调用DecisionAgent.make_decision()
    # 5. 调用ExecutionAgent.execute()
    # 6. 验证行为执行成功
    # 7. 验证事件生成
    # 8. 验证数据库记录
    pass

def test_full_workflow_without_instruction():
    """测试完整流程 - 无玩家指令"""
    # 1. 初始化游戏
    # 2. 不下达指令
    # 3. 调用3个Agent
    # 4. 验证自主行为选择
    # 5. 验证执行成功
    pass

def test_integration_with_governor_agent():
    """测试与GovernorAgent协作"""
    # 1. 初始化游戏
    # 2. Province Agent执行行为
    # 3. Governor Agent决定是否瞒报
    # 4. 验证三层数据模型正确
    pass
```

#### 3.2.3 边界条件测试

```python
# tests/test_edge_cases.py

def test_no_historical_data():
    """测试无历史数据情况"""
    # 新游戏，无历史数据
    # 验证Agent能够处理（使用默认值）
    pass

def test_instruction_not_feasible():
    """测试指令不可行情况"""
    # 忠诚度低时下达raise_tax指令
    # 验证Agent转为自主决策
    pass

def test_invalid_parameters():
    """测试非法参数情况"""
    # 参数超出范围
    # 验证Agent拒绝执行
    pass

def test_multiple_behaviors():
    """测试多个连续行为"""
    # 决策包含2个行为
    # 验证都能执行
    # 验证效果累加
    pass

def test_concurrent_agents():
    """测试多省份并发"""
    # 10个省份同时调用Agent
    # 验证无冲突
    # 验证性能可接受
    pass
```

#### 3.2.4 性能测试

```python
# tests/test_performance.py

def test_perception_agent_performance():
    """测试PerceptionAgent性能"""
    # 生成100个月历史数据
    # 测试perceive()执行时间
    # 验证 < 100ms
    pass

def test_decision_agent_performance():
    """测试DecisionAgent性能"""
    # 测试make_decision()执行时间
    # 验证 < 500ms
    pass

def test_execution_agent_performance():
    """测试ExecutionAgent性能"""
    # 测试execute()执行时间
    # 验证 < 200ms
    pass

def test_full_workflow_performance():
    """测试完整流程性能"""
    # 测试完整流程执行时间
    # 验证 < 1s
    pass
```

### 3.3 集成到现有系统

#### 3.3.1 修改Game.next_month()

```python
# /core/game.py

def next_month(self):
    """进入下个月"""
    current_month = self.state['current_month']
    current_year = (current_month - 1) // 12 + 1

    # ============ 新增：Province Agent流程 ============

    # 阶段1：感知阶段
    for province in self.provinces:
        perception = await self.perception_agents[province.province_id].perceive(
            province_id=province.province_id,
            current_month=current_month
        )
        # 保存perception到临时存储
        self._current_perceptions[province.province_id] = perception

    # 阶段2：决策阶段
    for province in self.provinces:
        # 获取待处理的玩家指令
        pending_instructions = self.db.get_pending_instructions(
            province.province_id,
            current_month,
            current_year
        )

        instruction = pending_instructions[0] if pending_instructions else None

        # 获取perception
        perception = self._current_perceptions[province.province_id]

        # 调用DecisionAgent
        decision = await self.decision_agents[province.province_id].make_decision(
            perception=perception,
            instruction=instruction,
            province_state=province.to_dict()
        )

        # 保存decision到临时存储
        self._current_decisions[province.province_id] = decision

    # 阶段3：执行阶段
    for province in self.provinces:
        decision = self._current_decisions[province.province_id]

        # 调用ExecutionAgent
        execution_result = await self.execution_agents[province.province_id].execute(
            decision=decision,
            province=province,
            month=current_month,
            year=current_year
        )

        # 保存执行结果
        self._current_execution_results[province.province_id] = execution_result

    # ============ 新增结束 ============

    # Phase 0: Agent生成事件（现有）
    # ... (保持不变)

    # Phase 1: 计算基础收支（现有）
    # ... (保持不变)

    # Phase 2: Agent决策（现有GovernorAgent）
    # ... (保持不变)

    # Phase 3: 预算执行（现有）
    # ... (保持不变)

    # Phase 4: 中央分析（现有）
    # ... (保持不变)

    # 下一月
    self.state['current_month'] += 1
```

#### 3.3.2 初始化Province Agents

```python
# /core/game.py

def __init__(self, db_path: str = "game.db", enable_central_advisor: bool = False):
    # ... (现有初始化代码)

    # ============ 新增：初始化Province Agents ============
    self._initialize_province_agents()
    # ============ 新增结束 ============
```

```python
def _initialize_province_agents(self) -> None:
    """初始化Province Agent系统"""
    print("Initializing Province Agents...")

    from agents.province.perception_agent import PerceptionAgent
    from agents.province.decision_agent import DecisionAgent
    from agents.province.execution_agent import ExecutionAgent

    self.perception_agents = {}
    self.decision_agents = {}
    self.execution_agents = {}
    self._current_perceptions = {}
    self._current_decisions = {}
    self._current_execution_results = {}

    for province in self.provinces:
        # 创建PerceptionAgent
        perception_agent = PerceptionAgent(
            agent_id=f"perception_{province.province_id}",
            config={
                'mode': 'rule_based',  # 默认规则模式
                'llm_config': {'enabled': False, 'mock_mode': True}
            },
            db=self.db
        )
        await perception_agent.initialize({})
        self.perception_agents[province.province_id] = perception_agent

        # 创建DecisionAgent
        decision_agent = DecisionAgent(
            agent_id=f"decision_{province.province_id}",
            config={
                'mode': 'rule_based',
                'llm_config': {'enabled': False, 'mock_mode': True}
            },
            db=self.db
        )
        await decision_agent.initialize({})
        self.decision_agents[province.province_id] = decision_agent

        # 创建ExecutionAgent
        execution_agent = ExecutionAgent(
            agent_id=f"execution_{province.province_id}",
            config={
                'mode': 'rule_based',
                'llm_config': {'enabled': False, 'mock_mode': True}
            },
            db=self.db,
            event_manager=self.event_manager,
            agent_event_generator=self.agent_event_generator
        )
        await execution_agent.initialize({})
        self.execution_agents[province.province_id] = execution_agent

        print(f"  Province {province.name}: Agents initialized")
```

### 3.4 配置和扩展性

#### 3.4.1 配置文件

```python
# /config/province_agent_config.py

PROVINCE_AGENT_CONFIG = {
    # 历史数据窗口配置
    'history_windows': {
        'recent_months': 1,      # 近期详细月数
        'quarterly_summaries': 4, # 季度摘要数量
        'annual_summaries': 3     # 年度摘要数量
    },

    # 关键事件索引配置
    'critical_events': {
        'indexed_categories': ['rebellion', 'war', 'disaster', 'crisis'],
        'max_events': 8           # 最多返回8个事件
    },

    # Token预算配置
    'token_budget': {
        'total': 4000,
        'recent_data_ratio': 0.4,    # 40%
        'summaries_ratio': 0.4,      # 40%
        'events_ratio': 0.2          # 20%
    },

    # 行为配置
    'behaviors': {
        'max_behaviors_per_decision': 2,  # 每次决策最多2个行为
        'default_duration': 6              # 默认持续时间
    },

    # LLM配置
    'llm': {
        'enabled': False,          # 是否启用LLM
        'model': 'claude-3-haiku-20240307',
        'max_tokens': 1024,
        'temperature': 0.1
    }
}
```

#### 3.4.2 扩展新行为

```python
# 添加新行为的步骤

# 1. 在behaviors.py中添加行为类型
class BehaviorType(str, Enum):
    # ... 现有行为
    CUSTOM_BEHAVIOR = "custom_behavior"  # 新行为

# 2. 在behavior_templates中添加模板
behavior_templates = {
    # ... 现有模板

    'custom_behavior': {
        'behavior_type': BehaviorType.CUSTOM_BEHAVIOR,
        'parameter_ranges': {
            'param1': (min_val, max_val),
            'param2': (min_val, max_val)
        },
        'default_duration': 6,
        'preconditions': {
            'min_loyalty': 50
        },
        'effects': {
            'effect1': 'formula',
            'effect2': 'formula'
        }
    }
}

# 3. 在ExecutionAgent中添加执行方法
async def _apply_custom_behavior(self, params, province):
    param1 = params.get('param1', default_val)
    param2 = params.get('param2', default_val)

    return {
        'effect1': calculated_value1,
        'effect2': calculated_value2
    }

# 4. 在_execute_behavior()中添加路由
async def _execute_behavior(self, behavior, province):
    if behavior.behavior_type == BehaviorType.CUSTOM_BEHAVIOR:
        return await self._apply_custom_behavior(behavior.parameters, province)
    # ... 现有路由
```

---

## 四、总结

### 4.1 架构优势

1. **清晰的职责分离**
   - PerceptionAgent专注于数据感知和趋势分析
   - DecisionAgent专注于决策逻辑和风险评估
   - ExecutionAgent专注于行为执行和效果计算
   - 每个Agent都可以独立测试和优化

2. **可扩展性**
   - 行为模板系统易于添加新行为类型
   - 历史数据管理策略可调整（通过配置文件）
   - LLM增强功能可选，不影响基础功能
   - 支持规则模式和LLM模式切换

3. **数据驱动**
   - 完善的历史数据管理（分层滑动窗口）
   - 关键事件索引支持快速检索
   - 行为历史记录用于未来决策参考
   - 统计指标支持智能决策

4. **兼容性**
   - 与现有GovernorAgent协作，不替代
   - 复用现有Event系统
   - 符合三层数据模型
   - 不破坏现有功能

### 4.2 实现建议

1. **渐进式开发**
   - 按Phase顺序实现
   - 每个Phase完成后进行测试
   - 及时修复bug
   - 避免大规模重构

2. **Mock优先**
   - 先实现规则模式
   - 使用mock数据测试
   - 验证数据流正确
   - 再添加LLM增强

3. **测试覆盖**
   - 每个Agent都要有单元测试
   - 集成测试验证端到端流程
   - 边界条件测试确保健壮性
   - 性能测试确保可接受

4. **文档完善**
   - 代码注释清晰
   - API文档完整
   - 使用示例丰富
   - 架构文档更新

### 4.3 预期成果

**功能完整性：**
- 能够读取和分析历史数据（分层摘要）
- 能够接收和评估玩家指令
- 能够执行预定义行为（5种类型）
- 能够生成月度报告和行为事件
- 能够与现有系统无缝集成

**性能要求：**
- 历史数据查询 < 100ms
- Agent决策 < 500ms
- 行为执行 < 200ms
- 完整流程 < 1s

**可维护性：**
- 单元测试覆盖率 > 80%
- 清晰的日志输出
- 完善的错误处理
- 灵活的配置选项

### 4.4 未来扩展方向

1. **更多行为类型**
   - 外交行为
   - 军事行为
   - 文化行为

2. **更智能的决策**
   - 强化学习优化
   - 多目标优化
   - 风险预测模型

3. **更丰富的交互**
   - 多模态输入（语音、图像）
   - 自然语言指令（更复杂）
   - 实时反馈系统

4. **更高级的Agent**
   - 多Agent协作
   - 层级Agent结构
   - 分布式Agent系统
