# 架构重构 v2（事件系统 + 预算系统）

## 1. 核心架构设计

### 1.1 模块结构

```
├── agents/                      # Agent决策层
│   ├── base.py                  # Agent基类，LLM基础设施
│   ├── personality.py           # 性格与能力数据模型
│   ├── governor_agent.py        # 地方治理Agent（生成事件、瞒报决策）
│   └── central_advisor.py       # 中央顾问Agent（分析、验证）
├── core/                        # 纯计算与数据层
│   ├── calculations.py          # 财务计算、预算执行计算
│   ├── province.py              # 省份数据类（三层数据模型）
│   ├── game.py                  # 游戏主循环
│   ├── budget_system.py         # 预算管理系统
│   ├── treasury_system.py       # 库存管理系统
│   └── budget_execution.py      # 预算执行引擎
├── db/                          # 数据持久化
│   ├── database.py              # 主数据库连接
│   └── event_database.py        # 事件数据库扩展
├── ui/                          # 用户界面
│   └── cli.py                   # 命令行界面
└── events/                      # 事件系统
    ├── event_models.py          # 事件数据模型（系统事件、Agent事件）
    ├── event_generator.py       # 系统事件生成器
    ├── agent_event_generator.py # Agent主动事件生成器
    ├── event_effects.py         # 事件效果计算
    ├── event_manager.py         # 事件生命周期管理
    └── overdraft_events.py      # 超支预定义事件模板
```

### 1.2 核心数据流

```
游戏循环 (core/game.py)
  ↓
阶段0: GovernorAgent生成事件（基于性格）
  ↓
阶段1: 计算基础收支（应用事件修正）
  ↓
阶段2: GovernorAgent决定瞒报（三层数据转换）
  ↓
阶段3: 预算执行（盈余分配 / 超支惩罚）
  ↓
阶段4: 中央顾问分析与国库结算
```

## 2. 三层数据模型

### 2.1 数据结构设计（Province类）

```python
# 第一层：真实值（游戏引擎计算得出）
actual_income: float           # 真实收入（计算得出）
actual_expenditure: float      # 真实支出（计算得出）

# 第二层：调整值（Agent决策后的值）
adjusted_income: float         # Agent调整后的收入（瞒报/夸大）
adjusted_expenditure: float    # Agent调整后的支出（虚增/虚减）
reporting_bias_ratio: float    # 调整比率（-0.5 ~ +0.5）
reporting_narrative: str       # 调整说明

# 第三层：上报值（最终提交给中央的值）
reported_income: float         # 最终上报收入
reported_expenditure: float    # 最终上报支出
is_fabricated: bool            # 是否编造事件

# 盈余计算（累计值）
actual_surplus: float          # 基于真实值的累计盈余
deported_surplus: float        # 基于上报值的累计盈余
```

### 2.2 数据流向

```
计算层
  ↓
基础收入 = f(人口, 发展度, 稳定度, 事件修正)
基础支出 = f(人口, 稳定度, 事件修正)
  ↓
实际收入/支出（实际值）
  ↓ (GovernorAgent决策)
adjusted_收入/支出 = 实际值 * (1 + bias_ratio)  # -0.5 ~ +0.5
  ↓ (最终上报)
上报收入/支出 = adjusted_值
cumulative_surplus += 本月盈余
```

### 2.3 数据更新时机

- **actual_值**：阶段1结束后更新（事件效果已应用）
- **adjusted_值**：阶段2结束后更新（Agent决策后）
- **reported_值**：阶段2结束后更新（通常等于adjusted_值）
- **surplus**：阶段3结束后更新（预算执行后）

## 3. Agent系统

### 3.1 GovernorAgent交互

#### 事件生成决策
```python
# GovernorAgent::generate_agent_event()
输入：
- province: Province对象（当前省份状况）
- game_state: Dict（全局游戏状态）
- current_month: int

输出：
- AgentEvent或None

决策逻辑：
1. 计算生成概率 = personality.event_generation_rate * 局势乘数
2. 如果随机数 < 概率：
   - 基于性格选择事件类型
   - 根据局势决定真实/编造
   - 创建事件对象
   - 返回AgentEvent
```

#### Reporting决策
```python
# GovernorAgent::decide_reporting()
输入：
- province: Province对象
- game_state: Dict

输出：
- ReportingDecision对象

流程：
1. 调用 _mock_llm_response() 或 _make_rule_based_decision()
2. 根据性格计算腐败概率
3. 生成bias_ratio(-0.5 ~ +0.5)和narrative
4. 应用调整到adjusted_值
5. 返回决策结果
```

#### 事件生成流程
```python
# Agent主动生成事件
if random() < generation_chance:
    event_type = select_by_personality()  # 根据性格选择
    event = create_event(event_type)

    # 决定是否编造
    if needs_cover or random() < fabrication_chance:
        event.is_fabricated = True

    # 决定是否隐藏
    if random() < hide_event_probability:
        event.visibility = 'hidden'

    return event
```

### 3.2 CentralAdvisorAgent交互

#### 月度分析
```python
# CentralAdvisorAgent::analyze_all_provinces()
输入：
- provinces: List[Province]
- game_state: Dict

流程：
1. 遍历所有省份
2. 计算可疑指标：
   - reporting_vs_actual偏差
   - 事件真实性评分
   - 历史一致性
3. 标记可疑省份
4. 生成分析报告

输出：
- AnalysisReport（可疑省份列表、风险等级）
```

#### 事件验证
```python
# CentralAdvisorAgent::verify_event()
输入：
- event: AgentEvent

流程：
1. 检查事件的叙事一致性
2. 评估支持证据的可信度
3. 基于历史数据验证效果值
4. 验证事件唯一性（检测重复事件）

输出：
- 可信度评分
- 验证结果
```

## 4. 事件系统

### 4.1 事件数据模型

```python
class Event(BaseModel):
    event_id: str                  # 唯一ID
    name: str
    description: str
    event_type: str                # 'national' | 'province'
    province_id: Optional[int]

    # 效果定义
    instant_effects: List[EventEffect]      # 即时效果（立即应用）
    continuous_effects: List[EventEffect]   # 持续效果（持续N个月）

    # 时间属性
    start_month: int
    end_month: Optional[int]
    is_active: bool

    # Agent生成标记
    is_agent_generated: bool = False
    is_fabricated: bool = False
    generated_by_agent_id: Optional[str]

class EventEffect(BaseModel):
    scope: EffectScope             # 'income', 'expenditure', 'loyalty', 'stability', 'development', 'population'
    operation: EffectOperation     # 'add', 'multiply'
    value: float                   # 效果值
```

### 4.2 事件生成机制

#### 系统事件生成（基础）
```python
# EventGenerator::generate_events()
输入：
- game_state: Dict
- provinces: List[Province]
- current_month: int

流程：
1. 遍历省份事件模板（12种类型）
2. 对每个事件，计算生成概率（基于省份特征）
3. 如果随机数 < 概率：
   - 创建事件
   - 添加到活跃事件列表
   - 返回事件列表
```

#### Agent事件生成（主动）
```python
# AgentEventGenerator::generate_agent_event()
输入：
- governor: GovernorAgent
- province: Province
- game_context: Dict

流程：
1. 评估局势，计算乘数（0-2）
2. 基于性格选择事件类型偏好
3. 判断是否需要掩盖（贪污检测）
4. 决定是否编造
5. 决定是否隐藏
6. 创建AgentEvent对象
```

### 4.3 事件效果应用

```python
# EventManager::apply_event_modifiers()
输入：
- province_id: int
- base_values: Dict（基础收入、支出）

流程：
1. 获取省份的活跃事件
2. 遍历所有持续效果
3. 按scope分类汇总效果
4. 应用乘性效果（乘法）
5. 应用加性效果（加法）
6. 返回最终修正值

公式：
结果值 = 基础值 × (1 + sum(乘性效果)) + sum(加性效果)
```

## 5. 预算系统

### 5.1 数据库设计

#### 年度预算表
```sql
CREATE TABLE annual_budgets (
    budget_id TEXT PRIMARY KEY,
    year INTEGER NOT NULL,
    province_id INTEGER,           -- NULL表示中央预算
    allocated_budget REAL NOT NULL, -- 预算金额
    actual_spent REAL DEFAULT 0,    -- 实际支出（累计）
    status TEXT DEFAULT 'active'    -- 'draft', 'active', 'completed'
)
```

#### 国库流水表
```sql
CREATE TABLE national_treasury_transactions (
    transaction_id TEXT PRIMARY KEY,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    type TEXT NOT NULL,           -- 'fixed_expense', 'event_expense',
                                  -- 'allocation_province', 'recall_province',
                                  -- 'surplus_allocation'
    amount REAL NOT NULL,
    province_id INTEGER,          -- 用于allocation/recall
    description TEXT,
    balance_after REAL NOT NULL   -- 交易后余额
)
```

#### 省库流水表
```sql
CREATE TABLE provincial_treasury_transactions (
    transaction_id TEXT PRIMARY KEY,
    province_id INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    type TEXT NOT NULL,           -- 'income', 'expenditure', 'central_allocation',
                                  -- 'surplus_allocation', 'transfer_to_national'
    amount REAL NOT NULL,
    description TEXT,
    balance_after REAL NOT NULL   -- 交易后余额
)
```

#### 盈余分配比例表
```sql
CREATE TABLE surplus_allocation_ratios (
    province_id INTEGER PRIMARY KEY,
    ratio REAL NOT NULL DEFAULT 0.5  -- 0.0-1.0，上交中央比例
)
```

### 5.2 预算执行流程

#### 月度执行（每月）
```python
# BudgetExecutor::execute_monthly_budget()
输入：
- provinces: List[Province]
- month: int
- year: int

流程：
对每个省份：
  1. 计算月度盈余 = reported_income - reported_expenditure
  2. 如果盈余 > 0：
     - ratio = get_allocation_ratio(province_id)  # 默认0.5
     - 上缴国库 = 盈余 × ratio
     - 入省库 = 盈余 × (1 - ratio)
     - 记录国库流水（surplus_allocation）
     - 记录省库流水（surplus_allocation）
  3. 如果盈余 < 0：
     - deficit = -盈余
     - 从省库扣除deficit
     - 如果省库余额不足：
       - 触发超支事件（财政危机/社会动荡/债务危机）
       - Agent决定是否上报
  4. 更新预算表actual_spent
```

#### 中央预算执行
```python
# BudgetExecutor::execute_central_budget()
输入：
- month: int
- year: int

流程：
1. 固定支出 = 200金币（每月）
2. 事件支出 = sum(中央级事件的支出效果)
3. 总支出 = 固定支出 + 事件支出
4. 从国库扣除
5. 如果国库余额不足：
   - 触发中央财政危机事件
```

#### 年度结转（12月）
```python
# BudgetExecutor::rollover_annual_surplus()
输入：
- year: int

流程：
1. 计算中央年度结余（国库余额 - 预算）
2. 为每个省份：
   - 计算省库年度结余
   - 创建流水记录（surplus_rollover）
3. 国库结余存入下年1月省库
4. 省库结余滚动到下年
```

### 5.3 资金划拨

#### 中央 → 省
```python
# TreasurySystem::transfer_from_national_to_province()
输入：
- province_id: int
- amount: float
- month: int
- year: int

流程：
1. 验证amount <= 国库余额
2. 国库扣款，记录流水（allocation_province）
3. 省库收款，记录流水（central_allocation）
4. 更新余额
```

#### 省 → 中央
```python
# TreasurySystem::transfer_from_province_to_national()
输入：
- province_id: int
- amount: float
- month: int
- year: int

流程：
1. 验证amount <= 省库余额
2. 省库扣款，记录流水（transfer_to_national）
3. 国库收款，记录流水（recall_province）
4. 更新余额
```

### 5.4 预算制定（12月）

```python
# BudgetSystem::generate_national_budget()
输入：
- year: int

流程：
1. 查询过去12个月中央实际支出
2. 平均值 = sum(支出) / 12
3. 预算 = 平均值 × 1.1（+10%缓冲）
4. 保存到annual_budgets表

# BudgetSystem::generate_provincial_budgets()
输入：
- year: int

流程：
对每个省份：
  1. 查询过去12个月实际支出
  2. 平均值 = sum(支出) / 12
  3. 预算 = 平均值 × 1.1
  4. 保存到annual_budgets表
```

## 6. 库存管理

### 6.1 国库管理

```python
# TreasurySystem::record_national_transaction()
输入：
- type: str
- amount: float
- description: str
- province_id: Optional[int]

流程：
1. 计算新余额 = 当前余额 + (收入类型) 或 - (支出类型)
2. 插入流水记录
3. 更新国库余额
4. 返回交易ID
```

### 6.2 省库管理

```python
# TreasurySystem::record_provincial_transaction()
输入：
- province_id: int
- type: str
- amount: float
- description: str

流程：
1. 查询省库当前余额
2. 计算新余额
3. 插入流水记录
4. 更新省库余额（provinces.provincial_treasury）
5. 返回交易ID
```

### 6.3 余额查询

```python
# 国库余额
balance = treasury_system.get_national_balance()

# 省库余额
balance = treasury_system.get_provincial_balance(province_id)

# 国库流水历史
transactions = treasury_system.get_national_transaction_history(limit=10)

# 省库流水历史
transactions = treasury_system.get_provincial_transaction_history(province_id, limit=10)
```

## 7. 超支惩罚机制

### 7.1 超支事件模板（overdraft_events.py）

```python
OVERDRAFT_EVENTS = [
    {
        'name': '财政危机',
        'description': '省份财政出现严重赤字，无法支付公务员工资',
        'severity': 0.9,
        'effects': [
            {'scope': 'stability', 'operation': 'multiply', 'value': -0.3},
            {'scope': 'loyalty', 'operation': 'add', 'value': -20}
        ]
    },
    {
        'name': '社会动荡',
        'description': '由于财政问题，民众开始抗议',
        'severity': 0.8,
        'effects': [
            {'scope': 'stability', 'operation': 'multiply', 'value': -0.4}
        ]
    },
    {
        'name': '债务危机',
        'description': '省份无法偿还到期债务',
        'severity': 0.95,
        'effects': [
            {'scope': 'development_level', 'operation': 'add', 'value': -0.5},
            {'scope': 'stability', 'operation': 'multiply', 'value': -0.5}
        ]
    }
]
```

### 7.2 超支处理流程

```python
# BudgetExecutor::handle_province_overdraft()
输入：
- province: Province
- deficit_amount: float

流程：
1. 检查省库余额
2. 如果余额 >= deficit_amount：
   - 从省库扣款
   - 记录支出流水
3. 否则：
   - 从省库扣光所有余额
   - 随机选择一个超支事件模板
   - 创建AgentEvent对象
   - 添加到事件管理器
   - Agent决定是否隐藏事件：
     * 如果隐藏：event.visibility = 'hidden'
     * 记录隐藏理由
     * province.hidden_events.append(event.event_id)
   - 应用事件效果（立即影响稳定度、忠诚度等）
```

### 7.3 中央超支处理

```python
# BudgetExecutor::handle_national_overdraft()
输入：
- deficit_amount: float

流程：
1. 检查国库余额
2. 如果余额不足：
   - 触发中央财政危机事件（national级别）
   - 影响全国稳定度和忠诚度
```

## 8. 年度流程

### 8.1 月度执行（1-11月）

1. 事件生成阶段（Agent主动）
2. 实际值计算阶段
3. Agent瞒报决策阶段
4. **预算执行阶段**（新增）
5. 中央顾问分析阶段
6. 国库结算阶段

### 8.2 12月特殊流程

```python
# 在 next_month() 中，当 month == 12 时：
1. 执行正常月度流程
2. 执行年度结转（rollover_annual_surplus）
3. 自动生成下年度预算：
   - BudgetSystem::generate_national_budget(year+1)
   - BudgetSystem::generate_provincial_budgets(year+1)
4. 弹出预算调整界面：
   - 显示建议值
   - 询问玩家是否调整
   - 确认并激活新预算
```

## 9. 数据交互

### 9.1 Province数据库交互

```python
# 从数据库加载省份（game.py::_load_provinces）
def _load_provinces(self) -> List[Province]:
    province_data = self.db.load_provinces()
    return [Province(data) for data in province_data]

# 保存省份（game.py::_save_provinces）
def _save_provinces(self) -> None:
    province_data = [p.to_dict() for p in self.provinces]
    self.db.save_provinces(province_data)
```

### 9.2 事件数据库交互

```python
# 保存事件（event_manager.py::save_event）
def save_event(self, event: Event) -> None:
    event_dict = event.dict()
    event_dict['instant_effects'] = json.dumps(event_dict['instant_effects'])
    event_dict['continuous_effects'] = json.dumps(event_dict['continuous_effects'])
    self.db.save_event(event_dict)

# 加载活跃事件（event_manager.py::load_active_events）
def load_active_events(self, current_month: int) -> List[Event]:
    event_data = self.db.get_active_events(current_month)
    return [Event(**data) for data in event_data]
```

### 9.3 库存数据库交互

```python
# 记录国库流水（treasury_system.py）
def record_national_transaction(self, month, year, type, amount, description):
    balance = self.get_national_balance()
    new_balance = balance + (amount if income else -amount)
    self.db.add_national_transaction({
        'transaction_id': f"nat_{month}_{year}_{uuid}",
        'month': month,
        'year': year,
        'type': type,
        'amount': amount,
        'description': description,
        'balance_after': new_balance
    })
    return new_balance

# 记录省库流水（treasury_system.py）
def record_provincial_transaction(self, province_id, month, year, type, amount, description):
    balance = self.get_provincial_balance(province_id)
    new_balance = balance + (amount if income else -amount)
    self.db.add_provincial_transaction({
        'transaction_id': f"prov_{province_id}_{month}_{year}_{uuid}",
        'province_id': province_id,
        'month': month,
        'year': year,
        'type': type,
        'amount': amount,
        'description': description,
        'balance_after': new_balance
    })
    # 更新省份表中的provincial_treasury字段
    self.db.update_province(province_id, {'provincial_treasury': new_balance})
    return new_balance
```

## 10. CLI界面扩展

### 10.1 主菜单（新增选项）

```
当前第 M 月 - 统治者控制台
============================================================
国库余额: XXXX.XX 金币
活跃事件: 全国N个, 省级M个

1. 查看财务报告
2. 管理省级项目
3. 切换Debug模式
4. 进入下一月
5. 查看省级事件
6. 查看全国状态（增强）
7. 资金管理（新增）
8. 查看预算执行（新增）
q. 退出游戏
```

### 10.2 资金管理界面（选项7）

```python
def fund_management():
    while True:
        print("\n=== 资金管理 ===")
        print("1. 中央拨款给省份")
        print("2. 省份上缴给中央")
        print("3. 设置各省盈余分配比例")
        print("4. 查看分配比例")
        print("5. 查看国库流水")
        print("6. 查看省库流水")
        print("0. 返回")

        choice = input("\n请选择操作: ").strip()

        if choice == '1':
            # 选择省份、输入金额、调用划拨函数
            province = select_province()
            amount = input("拨款金额: ")
            treasury_system.transfer_from_national_to_province(
                province.province_id, float(amount),
                self.game.state['current_month'],
                self.game.state['current_year']
            )

        elif choice == '2':
            # 选择省份、输入金额、调用上缴函数
            province = select_province()
            amount = input("上缴金额: ")
            treasury_system.transfer_from_province_to_national(
                province.province_id, float(amount),
                self.game.state['current_month'],
                self.game.state['current_year']
            )

        elif choice == '3':
            # 遍历所有省份
            for province in self.game.provinces:
                ratio = input(f"{province.name} 分配比例 (0.0-1.0): ")
                self.game.budget_system.set_allocation_ratio(
                    province.province_id, float(ratio)
                )

        elif choice == '4':
            # 显示所有省份的分配比例
            ratios = self.game.budget_system.get_all_allocation_ratios()
            for province_id, ratio in ratios.items():
                province = self.game.get_province(province_id)
                print(f"{province.name}: {ratio:.2f} (上交中央)")

        elif choice == '0':
            break
```

### 10.3 预算执行查看（选项8）

```python
def show_budget_execution():
    print(f"\n{'='*70}")
    print("预算执行情况")
    print(f"{'='*70}")

    # 中央预算
    central_budget = budget_system.get_national_budget(current_year)
    print(f"\n中央财政:")
    print(f"  预算总额: {central_budget.allocated_budget:.2f}")
    print(f"  已执行: {central_budget.actual_spent:.2f}")
    print(f"  执行率: {central_budget.actual_spent / central_budget.allocated_budget:.1%}")

    # 各省预算
    for province in provinces:
        prov_budget = budget_system.get_provincial_budget(province.province_id, current_year)
        print(f"\n【{province.name}】")
        print(f"  预算总额: {prov_budget.allocated_budget:.2f}")
        print(f"  已执行: {prov_budget.actual_spent:.2f}")
        print(f"  执行率: {prov_budget.actual_spent / prov_budget.allocated_budget:.1%}")

    input("\n按Enter继续...")
```

### 10.4 12月自动预算调整

```python
# 在 next_month() 中，当 month == 12 时：
if current_month == 12:
    print(f"\n{'='*60}")
    print(f"  财政年度结束 - 制定 {current_year + 1} 年度预算")
    print(f"{'='*60}")

    # 显示当前年度执行情况
    show_annual_execution_summary()

    # 生成建议值（基于历史数据）
    advice = budget_system.generate_budget_advice(current_year + 1)
    print("\n[中央顾问建议]")
    print(f"  中央预算: {advice['national']:.2f} (基于平均值+10%缓冲)")
    for prov_id, prov_advice in advice['provinces'].items():
        province = get_province(prov_id)
        print(f"  {province.name}: {prov_advice:.2f}")

    # 询问是否调整
    adjust = input("\n是否调整预算？(y/n): ").strip()
    if adjust.lower() == 'y':
        # 中央预算调整
        adj = input("中央预算调整 (+/-金额): ")
        budget_system.adjust_national_budget(current_year + 1, float(adj))

        # 各省预算调整
        for province in provinces:
            adj = input(f"{province.name} (+/-金额): ")
            budget_system.adjust_provincial_budget(
                province.province_id, current_year + 1, float(adj)
            )

    # 确认并激活
    confirm = input("\n确认并激活新预算？(y/n): ").strip()
    if confirm.lower() == 'y':
        budget_system.activate_budgets(current_year + 1)
        print("✓ 新预算已激活")
```

## 11. 核心文件清单

**Agent层（1200行）：**
- agents/base.py: 180行（Agent基类、LLM接口）
- agents/personality.py: 250行（性格与能力数据模型）
- agents/governor_agent.py: 500行（事件生成、瞒报决策）
- agents/central_advisor.py: 300行（分析、验证、预算建议）

**核心层（1200行）：**
- core/calculations.py: 300行（财务计算、事件效果计算）
- core/province.py: 200行（省份数据类、三层数据模型）
- core/game.py: 400行（游戏循环、流程编排）
- core/budget_system.py: 300行（预算管理、年度预算生成）
- core/treasury_system.py: 300行（库存管理、流水记录）
- core/budget_execution.py: 250行（预算执行、超支处理）

**事件系统（800行）：**
- events/event_models.py: 200行（事件数据模型）
- events/event_generator.py: 150行（系统事件生成）
- events/agent_event_generator.py: 200行（Agent主动事件生成）
- events/event_effects.py: 150行（效果计算）
- events/event_manager.py: 150行（事件生命周期管理）
- events/overdraft_events.py: 100行（超支事件模板）

**数据层（扩展）：**
- db/database.py: 扩展（库存流水表、预算表）
- db/event_database.py: 200行（事件数据库操作）

**UI层：**
- ui/cli.py: 扩展（资金管理界面、预算查看界面）

**总计：**约3500行代码

## 12. 系统特性

### 12.1 核心特性

1. **三层数据模型**：真实值 → 调整值 → 上报值
2. **Agent性格系统**：6种性格类型影响行为
3. **主动事件生成**：15种Agent事件类型（可真实可编造）
4. **预算执行系统**：年度预算、月度执行、盈余分配
5. **三层库存管理**：国库、省库、详细流水记录
6. **超支惩罚机制**：赤字触发严重事件（Agent决定是否上报）
7. **资金双向划拨**：中央↔省份手动划拨
8. **事件可见性控制**：PUBLIC/PROVINCIAL/HIDDEN
9. **纯函数计算**：无副作用，易于测试
10. **完整审计追踪**：所有财务操作都有流水记录

### 12.2 数据完整性

- 所有事件都有完整生命周期记录
- 所有库存变动都有流水记录
- 预算执行全程可追踪
- 所有Agent决策都有日志记录

## 13. 实时仪表盘CLI（简化版）

### 13.1 设计理念

**简化实现：**
- 移除自动刷新（原每2秒刷新）
- 改为返回主菜单时刷新（draw_dashboard()重写）
- 使用同步方式，移除asyncio依赖

**优势：**
- 更简单，无后台任务
- 更低资源占用
- 用户体验更清晰（用户控制刷新时机）

### 13.2 界面布局

```
================================================================================
EU4风格策略游戏 - 实时仪表盘
================================================================================

游戏时间: 第 N 月 (第 Y 年)
国库余额:   XXXXX.XX 金币
Debug模式: [开启/关闭]

活跃事件: 全国 N 个, 省级 N 个

────────────────────────────────────────────────────────────────────────────────
预算执行情况:
────────────────────────────────────────────────────────────────────────────────
中央预算:
  总额:    XXXXX.XX 金币
  已执行:  XXXXX.XX 金币
  剩余:    XXXXX.XX 金币
  执行率:     XX.X%

────────────────────────────────────────────────────────────────────────────────
省份概况:
────────────────────────────────────────────────────────────────────────────────

省份           忠诚度      稳定度      省库余额         状态
──────────── ──────── ──────── ──────────── ────────────────────
首都          90       85       458.59       [正常](绿色)
边境省        50       60       985.40       [瞒报中](红色)
北方省        70       70       810.06       [正常](绿色)

────────────────────────────────────────────────────────────────────────────────
操作菜单:
────────────────────────────────────────────────────────────────────────────────
  1. 财务报告  2. 项目管理  3. 切换Debug  4. 下一月  5. 省级事件
  6. 全国状态  7. 资金管理  8. 预算执行  9. 刷新  Q. 退出

最后更新: HH:MM:SS (按数字进入菜单，Q退出)
```

**颜色编码：**
- 🟢 绿色：正常状态、开启状态、正常数值
- 🟡 黄色：警告状态、数值数据
- 🔴 红色：异常状态、关闭状态、瞒报中

### 13.3 刷新机制

**关键点：**
1. **清屏重绘：** `draw_dashboard()`使用`\033[2J\033[H`清屏
2. **返回刷新：** 所有子菜单返回后调用`draw_dashboard()`
3. **状态实时：** 每次重绘都读取最新的游戏状态

**代码流程：**
```python
def run(self):
    while True:
        self.draw_dashboard()          # 1. 绘制仪表盘
        choice = input("操作: ")       # 2. 等待用户输入
        self.handle_choice(choice)     # 3. 处理选择
        # 循环回到1，重绘仪表盘（刷新）

def handle_choice(self, choice):
    if choice == '1':
        self.show_financial_report()  # 显示报告
        input("返回...")              # 等待用户
                                    # 返回后run()会重绘仪表盘
```

### 13.4 使用方式

```bash
# 传统CLI（静态界面）
uv run python main.py

# 仪表盘CLI（返回时刷新）
uv run python main.py --realtime
# 或
uv run python main.py -r
```
