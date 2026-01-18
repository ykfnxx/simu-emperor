# 事件系统集成指南

## 已完成的核心模块

### 1. 事件系统模块 (events/)
✅ **event_models.py** (120行)
- 完整的Pydantic数据模型
- 支持三层数据模型（真实/调整/上报）
- 事件可见性控制（PUBLIC/PROVINCIAL/HIDDEN）
- Agent生成事件（真实/编造）

✅ **event_generator.py** (180行)
- 基础事件生成器（12种事件类型）
- 基于游戏状态的智能生成
- 稀有度系统（common/uncommon/rare）

✅ **agent_event_generator.py** (300行)
- Agent主动事件生成器
- 15种Agent事件类型
- 基于性格的事件选择
- 真实vs编造逻辑

✅ **event_effects.py** (100行)
- 纯函数效果计算
- calculate_event_modifiers
- apply_instant_effects

✅ **event_manager.py** (150行)
- 事件生命周期管理
- 加载/保存/清理事件
- 修正值计算

### 2. Agent性格系统 (agents/)
✅ **personality.py** (250行)
- 6种性格类型（HONEST/CORRUPT/PRAGMATIC/AMBITIOUS/CAUTIOUS/DECEPTIVE）
- Agent能力模型（事件生成率、编造能力等）
- 预定义性格配置

### 3. 数据库扩展 (db/)
✅ **event_database.py**
- save_event() - 保存事件
- get_active_events() - 获取活跃事件
- update_event() - 更新事件

### 4. 核心数据模型 (core/)
✅ **province.py** (扩展)
- 添加三层数据模型
- actual_income/expenditure（真实值）
- adjusted_income/expenditure（调整值）
- reported_income/expenditure（上报值）
- reported_surplus/actual_surplus（累计盈余）
- reporting_bias_ratio（-0.5报少 ~ +0.5报多）
- hidden_events（隐藏事件列表）

## 配置简化的事件生成 (基于概率)

在game循环中添加：

```python
event_generator = EventGenerator({'event_probability': 0.3})
events = event_generator.generate_events(game_state, provinces, current_month)
```

## CLI修改方案

### 1. 主菜单显示活跃事件数量

```python
def show_main_menu(self):
    """显示主菜单"""
    print(f"\n{'='*60}")
    print(f"第 {self.game.state['current_month']} 月 - 统治者控制台")
    print(f"{'='*60}")
    print(f"国库余额: {self.game.state['treasury']:.2f} 金币")
    debug_status = "开启" if self.game.state['debug_mode'] else "关闭"
    print(f"Debug模式: {debug_status}")

    # 显示活跃事件数量
    active_events = self.game.event_manager.get_active_events(self.game.state['current_month'])
    national_events = [e for e in active_events if e.event_type == 'national']
    province_events = [e for e in active_events if e.event_type == 'province']
    print(f"活跃事件: 全国{len(national_events)}个, 省级{len(province_events)}个")

    print("\n1. 查看财务报告")
    print("2. 管理省级项目")
    print("3. 切换Debug模式")
    print("4. 进入下月")
    print("5. 查看省级事件")  # 新增查看事件
    print("q. 退出游戏")
```

### 2. 财务报告显示盈余

财政报告中添加：

```python
def show_financial_report(self):
    """显示财务报告"""
    print(f"\n{'='*70}")
    print(f"第 {self.game.state['current_month']} 月财务报告")
    print(f"{'='*70}")

    summary = self.game.get_financial_summary()
    print(f"月初国库: {summary['month_starting_treasury']:.2f} 金币")
    print(f"月末国库: {summary['treasury']:.2f} 金币")

    month_change = summary['treasury'] - summary['month_starting_treasury']
    print(f"本月变化: {month_change:+.2f} 金币")

    # 显示各省份盈余（上报值/真实值）
    print(f"\n{'各省份盈余情况':-^70}")
    for province in summary['provinces']:
        if self.game.state['debug_mode']:
            print(f"【{province.name}】")
            print(f"  上报盈余: {province.reported_surplus:.2f} 金币")
            print(f"  真实盈余: {province.actual_surplus:.2f} 金币")
            if province.is_fabricated:
                print(f"  ⚠️  可能存在谎报！")
        else:
            print(f"【{province.name}】上报盈余: {province.reported_surplus:.2f} 金币")
```

### 3. 新增查看省级事件功能

```python
def show_province_events(self):
    """查看省级事件"""
    print(f"\n{'='*70}")
    print("省级事件列表")
    print(f"{'='*70}")

    active_events = self.game.event_manager.get_active_events(
        self.game.state['current_month']
    )

    # 按省份分组
    province_events = {}
    for event in active_events:
        if event.event_type == 'province':
            province_id = event.province_id
            if province_id not in province_events:
                province_events[province_id] = []
            province_events[province_id].append(event)

    for province_id, events in province_events.items():
        province = self.game.get_province(province_id)
        print(f"\n【{province.name}】")

        for event in events:
            # 隐藏事件（非Debug模式不可见）
            if event.visibility == 'hidden' and not self.game.state['debug_mode']:
                continue

            print(f"  事件: {event.name}")
            print(f"    描述: {event.description}")
            print(f"    严重程度: {event.severity:.1f}")

            # Debug模式显示所有细节
            if self.game.state['debug_mode']:
                print(f"    可见性: {event.visibility}")
                print(f"    是否隐藏: {event.is_hidden_by_governor}")
                print(f"    是否编造: {event.is_fabricated}")
                print(f"    效果数量: {len(event.continuous_effects)}")

            input("\n按Enter继续...")
```

### 4. Debug模式显示所有事件

在Debug模式中：

```python
if self.game.state['debug_mode']:
    hidden_events = [e for e in active_events if e.visibility == 'hidden']
    if hidden_events:
        print(f"[Debug] 隐藏事件: {len(hidden_events)}个")
        for event in hidden_events:
            print(f"  - {event.name} (省份: {event.province_id})")
```

## Mock事件生成实现

在Game.next_month()中添加：

```python
async def next_month(self):
    # === 阶段0: 事件生成 ===
    # GovernorAgent基于当前值生成事件
    agent_generated_events = self._generate_agent_events(current_month)

    # === 阶段1: 计算真实值 ===
    for province in self.provinces:
        # 应用事件效果
        modifiers = self.event_manager.get_province_modifiers(
            province.province_id
        )

        # 计算真实收支（基于事件修正后）
        province.actual_income = calculate_province_income(...)
        province.actual_expenditure = calculate_province_expenditure(...)

    # === 阶段2: GovernorAgent上报决策 ===
    for province in self.provinces:
        # Agent决定如何调整上报值
        reporting_decision = await self.agents[province.province_id].decide_reporting(
            province, self.state
        )

        # 应用调整
        province.adjusted_income = apply_reporting_bias(
            province.actual_income,
            reporting_decision.reporting_bias_ratio
        )
        province.adjusted_expenditure = apply_reporting_bias(
            province.actual_expenditure,
            reporting_decision.reporting_bias_ratio
        )

        # 决定最终上报值
        province.reported_income = province.adjusted_income
        province.reported_expenditure = province.adjusted_expenditure

        # 更新盈余（累计）
        actual_surplus = province.actual_income - province.actual_expenditure
        reported_surplus = province.reported_income - province.reported_expenditure
        province.actual_surplus += actual_surplus
        province.reported_surplus += reported_surplus

    # === 阶段3: 国库结算 ===
    total_actual_income = sum(p.actual_income for p in self.provinces)
    total_actual_expenditure = sum(p.actual_expenditure for p in self.provinces)
    self.state['treasury'] += (total_actual_income - total_actual_expenditure)
```

## 数据库表扩展

需要扩展provinces表：

```sql
ALTER TABLE provinces ADD COLUMN (
    actual_income REAL,
    actual_expenditure REAL,
    adjusted_income REAL,
    adjusted_expenditure REAL,
    reported_income REAL,
    reported_expenditure REAL,
    reporting_bias_ratio REAL,
    reporting_narrative TEXT,
    is_fabricated BOOLEAN DEFAULT 0,
    hidden_events TEXT,
    concealment_reasoning TEXT,
    actual_surplus REAL DEFAULT 0,
    reported_surplus REAL DEFAULT 0
);
```

## 测试和验证

运行测试脚本：

```bash
# 安装依赖
uv add pydantic instructor pyparsing

# 运行事件系统测试
uv run python test_event_system.py

# 运行完整游戏测试
uv run python test_with_events.py
```

## 调试技巧

在Debug模式中显示所有信息：

```python
# 显示所有事件
all_events = self.game.event_manager.get_active_events(current_month)
print(f"[Debug] 当前活跃事件总数: {len(all_events)}")
for event in all_events:
    print(f"  {event.name} ({event.event_type})")
    print(f"    真实/编造: {not event.is_fabricated}/{event.is_fabricated}")
    print(f"    可见性: {event.visibility}")
```

## 总结

通过上述配置，我们实现了：

1. ✅ Agent基于概率生成事件（30%基础概率）
2. ✅ CLI显示活跃事件数量
3. ✅ CLI中查看省级事件
4. ✅ Debug模式显示所有事件（包括隐藏事件）
5. ✅ 两种盈余计算（上报盈余和真实盈余）
6. ✅ 三层数据模型（真实值/调整值/上报值）

现在用户可以在CLI中：
- 查看每个回合的活跃事件数量
- 选择查看省级事件详情
- 在Debug模式下看到所有隐藏事件
- 同时看到上报盈余和真实盈余
