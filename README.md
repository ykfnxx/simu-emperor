# EU4-Style Strategy Game

A turn-based grand strategy game framework inspired by Europa Universalis 4, where players act as a ruler managing multiple provinces through budget allocation and project investments.

## Game Features

### Core Mechanics

1. **Turn-based Cycle**: Monthly turns with automatic provincial income/expenditure calculations
2. **Information Asymmetry**: Local officials may conceal data, requiring players to detect anomalies
3. **Three-Layer Data Model**: Actual → Adjusted → Reported values
4. **Project Investments**: 4 types of projects to influence provincial development
5. **Budget System**: Annual budget allocation and execution tracking
6. **Dual Treasury System**: Separate national and provincial treasuries
7. **Event System**: Dynamic national and provincial events with effects
8. **Debug Mode**: Toggle between player view and actual data for testing

### Province System

Each province has:
- **Population**: Affects tax revenue and expenditure
- **Development Level**: 1-10 scale affecting production efficiency
- **Loyalty**: 0-100, affects misreporting probability
- **Stability**: 0-100, affects security costs
- **Base Income**: Agriculture + industry/commerce output
- **Three-Layer Values**:
  - Actual: Real calculated values
  - Adjusted: After Governor modifications
  - Reported: Final values reaching central government

### AI Governor System

Each province is managed by an AI Governor with personality traits:

**Misreporting Mechanism**:
- Base 30% corruption tendency
- Lower loyalty increases corruption chance
- Income concealed by 10-30%
- Expenditure inflated by 5-20%
- Can fabricate events

**Personality Types**:
- `honest`: Rarely misreports (-20% corruption tendency)
- `corrupt`: Frequently misreports (+30% corruption tendency)
- `pragmatic`: Balanced approach
- `ambitious`: May take risks to impress central government

**Decision Logic**:
- Triggered events based on corruption tendency
- Choice to hide events (affecting player visibility)
- Budget execution bias based on loyalty and personality

### Event System

**Two Event Types**:
1. **National Events**: Affect all provinces and central treasury
   - Economic crises
   - Natural disasters
   - Political turmoil

2. **Provincial Events**: Affect specific provinces
   - Local incidents
   - Development opportunities
   - Stability challenges

**Event Attributes**:
- Name, description, severity (1-10)
- Duration in months
- Continuous effects on income/expenditure
- Can be permanent or temporary

**Event Effects**:
- Income multipliers/dividers
- Expenditure modifications
- Loyalty/stability changes
- Special triggers for fiscal crises

### Project System

Players can invest in 4 project types:

1. **Agricultural Reform** (Cost: 50 gold)
   - Effect: Base income +8%

2. **Infrastructure Development** (Cost: 80 gold)
   - Effect: Development level +0.5

3. **Tax Relief** (Cost: 30 gold)
   - Effect: Loyalty +15

4. **Security Enhancement** (Cost: 60 gold)
   - Effect: Stability +12

Projects take effect on the **next monthly calculation**.

### Budget Execution System

**Annual Budget Cycle**:
1. Budget planning (draft status)
2. Budget activation (active status)
3. Monthly execution tracking
4. Year-end surplus/deficit processing

**Surplus Allocation**:
- Each province has configurable allocation ratio (0.0-1.0)
- Ratio determines split between provincial and national treasury
- 0.0 = Keep all locally, 1.0 = Transfer all to national

**Overdraft Handling**:
- Provincial deficits deducted from provincial treasury
- Central deficits trigger fiscal crisis events
- AI Governors may hide overdraft events

### Treasury System

**Two-Tier Structure**:
- **National Treasury**: Central government funds
- **Provincial Treasuries**: Local government funds per province

**Transaction Types**:
- Central allocation to provinces
- Provincial remittance to central
- Surplus allocation
- Regular income/expenditure
- Project funding

## Installation and Running

### Requirements

- Python 3.8+
- SQLite3 (built into Python)
- Required packages: See `requirements.txt`

### Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd eu4-strategy-game
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the game:
```bash
python main.py
```

4. Optional: Use real-time CLI interface:
```bash
python -m ui.cli_realtime
```

## Gameplay

### Main Menu

```
============================================================
Month 1 - Ruler Console
============================================================
Treasury Balance: 1000.00 gold
Debug Mode: Disabled

Active Events: 2 national, 3 provincial

1. View Financial Report
2. Manage Provincial Projects
3. Toggle Debug Mode
4. Next Month
5. View Provincial Events
6. View National Status
7. Fund Management
8. View Budget Execution
q. Quit Game
```

### Feature Guide

#### 1. View Financial Report

Displays last month's financial data:

- **Treasury Balance**: Current national treasury
- **Monthly Change**: Month-over-month difference
- **Provincial Reports**: Income, expenditure, surplus per province

**Debug Mode ON**: Shows Actual/Reported comparison with concealment amounts
```
【Northern Province】
  Income: 480.00 / 600.00 gold
  Expenditure: 250.00 / 220.00 gold
  ⚠️  Officials concealed 120.00 gold in income!
```

**Debug Mode OFF**: Shows only reported values (real gameplay)
```
【Northern Province】 Income: 480.00, Expenditure: 250.00, Surplus: 230.00 gold [Abnormal]
```

#### 2. Manage Provincial Projects

Invest in province projects:

1. Select province
2. Select project type (1-4)
3. Confirm cost and deduct from treasury

Example:
```
=== Initiate Provincial Projects ===

Select Province:
1. Capital
> 1

Project Type:
1. Agricultural Reform (Cost: 50 gold) - Increase base income by 8%
2. Infrastructure Development (Cost: 80 gold) - Development level +0.5
3. Tax Relief (Cost: 30 gold) - Loyalty +15
4. Security Enhancement (Cost: 60 gold) - Stability +12
> 4

✓ Project started in Capital!
  Project Type: Security Enhancement
  Cost: 60 gold
  Effect: Stability +12
```

#### 3. Toggle Debug Mode

For development/testing: Toggle view between reported and actual data

#### 4. Next Month

Execute monthly calculation:
1. Process active project effects
2. Calculate real provincial income/expenditure
3. AI Governor decides whether to misreport
4. Apply event effects
5. Execute budget allocations
6. Update treasury balances
7. Record monthly reports
8. Detect deficits and trigger events

#### 5. View Provincial Events

Display current provincial events: Active events per province with descriptions, severity levels, and effects.

#### 6. View National Status

Comprehensive overview:
- Treasury summary
- National revenue/expenditure statistics
- Provincial overview with status indicators
- Active national and provincial events
- Event effect details

#### 7. Fund Management

Advanced treasury operations:
1. Transfer to Province (central → provincial)
2. Transfer from Province (provincial → central)
3. Set Surplus Allocation Ratios (per province)
4. View Allocation Ratios
5. View National Transaction History
6. View Provincial Transaction History

#### 8. View Budget Execution

Budget tracking and reporting:
- Central budget execution rate
- Provincial budget execution per province
- Remaining funds and expenditure tracking

### Game Strategy

#### Detecting Misreporting

1. **Abnormal Indicators**: CLI shows `[Abnormal]` tag for provinces with last month's corruption
2. **Loyalty/Stability Drops**: Sudden decreases may indicate problems
3. **Event Visibility**: Some events may be hidden by corrupt officials
4. **Budget Discrepancies**: Execution rates that don't match plans

#### Reducing Corruption

1. **Tax Relief Projects**: +15 loyalty per project
2. **Security Enhancement**: +12 stability per project
3. **Monitor High-Risk Provinces**: Low loyalty = high corruption risk
4. **Use Debug Mode**: For testing and verification (development)

#### Budget Management

1. **Allocation Ratios**: Balance between local retention and central collection
2. **Strategic Investments**: Prioritize high-return provinces
3. **Event Reserves**: Keep treasury buffer for crisis events
4. **Deficit Avoidance**: Prevent fiscal crises that trigger negative events

## Project Structure

```
.
├── main.py                      # Game entry point
├── core/
│   ├── __init__.py
│   ├── game.py                 # Game main loop and state
│   ├── province.py             # Province data model (three-layer)
│   ├── project.py              # Project system
│   ├── calculations.py         # Income/expenditure calculations
│   ├── budget_system.py        # Budget allocation and planning
│   ├── budget_execution.py     # Monthly budget execution
│   └── treasury_system.py      # National/provincial treasuries
├── agents/
│   ├── __init__.py
│   ├── base.py                 # Base agent class
│   ├── governor_agent.py       # Provincial governor AI
│   ├── central_advisor.py      # Central advisor AI
│   └── personality.py          # Personality traits system
├── events/
│   ├── __init__.py
│   ├── event_manager.py        # Event lifecycle management
│   ├── event_generator.py      # Event generation system
│   ├── agent_event_generator.py # AI-triggered events
│   ├── event_effects.py        # Effect application logic
│   └── overdraft_events.py     # Fiscal crisis events
├── db/
│   ├── __init__.py
│   ├── database.py             # Database interface
│   └── event_database.py       # Event storage
├── ui/
│   ├── __init__.py
│   ├── cli.py                  # Standard CLI interface
│   └── cli_realtime.py         # Real-time dashboard CLI
└── game.db                     # SQLite database (auto-generated)
```

### Database Schema

**provinces**: Province attributes and three-layer data model
**game_state**: Game state (month, treasury, debug_mode, current_budget_year)
**projects**: Active projects
**national_budgets**: Central annual budgets
**provincial_budgets**: Provincial annual budgets
**national_treasury_transactions**: National treasury transaction history
**provincial_treasury_transactions**: Provincial treasury transaction history
**events**: Event definitions and active events
**event_effects**: Event effect definitions
**surplus_allocation_ratios**: Per-province allocation ratios

## Technical Architecture

### Key Design Patterns

1. **Three-Layer Data Model**:
   ```python
   actual_values → adjusted_values → reported_values
   # Each layer can be manipulated independently
   ```

2. **Agent-Centric Design**: Each province has its own AI agent
   - Independent decision making
   - Personality-based behavior
   - Misreporting and event handling

3. **Event-Driven System**:
   - Dynamic event generation
   - Continuous and one-time effects
   - Hidden/fabricated event support

4. **Pure Data Classes**: Province and Project are data-only classes
   - Single Responsibility Principle
   - Easy serialization
   - Clear separation from business logic

### Extension Points

1. **New Project Types**: Add to `Project.PROJECT_TYPES`
2. **New Events**: Create event templates in `events/`
3. **New Agent Types**: Extend `BaseAgent`
4. **New Effects**: Implement in `event_effects.py`

## Development

### Debugging

Enable Debug Mode:
```python
# In game_state table set debug_mode = 1
game.toggle_debug_mode()  # Or use menu option
```

### Balance Tuning

Key parameters in:
- `core/calculations.py`: Income/expenditure coefficients
- `agents/personality.py`: Corruption probabilities
- `core/project.py`: Project costs and effects
- `events/event_templates.py`: Event effects

### Testing

Run tests:
```bash
# Test event system
python test_event_system.py

# Test budget system
python test_budget_system.py

# Full verification
python verify_conversion.py
```

## Development Roadmap

### Completed MVP Features

✅ Basic province management
✅ AI Governor system with misreporting
✅ Three-layer data model
✅ Four project types
✅ Budget allocation system
✅ Dual treasury system
✅ Event system (national + provincial)
✅ AI personality traits
✅ Debug mode toggle
✅ Real-time CLI interface

### Potential Extensions

- Counter-corruption mechanics (data anomaly detection, audits)
- Military system (recruitment, warfare, occupation)
- Diplomacy system (alliances, trade, treaties)
- Dynamic province borders and conquest
- Multiplayer support
- Web-based GUI
- AI players for single-player
- Economic policy system (tax rates, tariffs)
- Technology/research system
- Population happiness mechanics

## Sample Game Flow

```bash
$ python main.py

# View first month report (Debug mode ON)
> 1
[Debug] Provincial Status (Reported / Actual)
【Northern Province】 ⚠️ Officials concealed 120.00 gold in income!

# Invest in project
> 2
Select Province: 2
Project Type: 4  # Security Enhancement

# Turn off Debug mode for real gameplay
> 3
Debug Mode disabled

# Advance to next month
> 4
✓ Month 2 calculation complete!
```

## License

MIT License

## Authors

AI Assistant + Human Collaboration

## Contributing

This is a demonstration project. Feel free to fork and extend!
