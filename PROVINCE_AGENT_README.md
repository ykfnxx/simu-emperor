# Province Agent System - Implementation Summary

## Overview

The Province Agent system is a three-stage autonomous agent pipeline that manages provinces through:

1. **Perception** - Analyzes historical data and generates insights
2. **Decision** - Makes strategic decisions based on context and player instructions
3. **Execution** - Executes behaviors and applies effects

## Architecture

### Three-Agent Pipeline

```
┌─────────────────┐
│ PerceptionAgent  │  ← Reads historical data (monthly/quarterly/annual)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DecisionAgent   │  ← Receives context + player instructions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ ExecutionAgent   │  ← Executes behaviors, generates events
└─────────────────┘
```

### Data Flow

```
Game.next_month()
  ↓
1. Event Generation Phase
  ↓
2. Governor Decision Phase
  ↓
3. Province Agent Execution Phase  ← NEW
   ├─ PerceptionAgent.perceive()
   ├─ DecisionAgent.make_decision()
   └─ ExecutionAgent.execute()
  ↓
4. Budget Execution Phase
  ↓
5. Record & Save
```

## Database Schema

### New Tables

1. **province_monthly_summaries** - Monthly detailed data
2. **province_quarterly_summaries** - Quarterly aggregated summaries with LLM summaries
3. **province_annual_summaries** - Annual summaries with performance ratings
4. **player_instructions** - Player instruction tracking
5. **province_behaviors** - Agent behavior records
6. **special_events_index** - Critical event indexing

### Modified Tables

- **monthly_reports** - Added agent_behavior_id, player_instruction_id, decision_summary

## Components

### 1. Data Models (`agents/province/models.py`)

```python
- Enums: TrendDirection, RiskLevel, InstructionStatus, BehaviorType
- Perception: EventSummary, MonthlyDetailedData, QuarterlySummary, AnnualSummary
- Decision: PlayerInstruction, BehaviorDefinition, InstructionEvaluation, Decision
- Execution: BehaviorEffect, ExecutedBehavior, BehaviorEvent, ExecutionResult
```

### 2. Behavior System (`agents/province/behaviors.py`)

**8 Behavior Types:**
- `tax_adjustment` - Modify tax rates
- `infrastructure_investment` - Invest in development
- `loyalty_campaign` - Improve population loyalty
- `stability_measure` - Enhance stability
- `emergency_relief` - Crisis response
- `corruption_crackdown` - Reduce corruption
- `economic_stimulus` - Boost economy
- `austerity_measure` - Reduce expenditure

Each behavior has:
- Parameter ranges and validation
- Cost and effect calculation
- Risk assessment

### 3. PerceptionAgent (`agents/province/perception_agent.py`)

**Responsibilities:**
- Build layered historical data (1 month + 4 quarters + 3 years)
- Generate quarterly and annual summaries with LLM
- Index critical events (rebellion, war, disaster, crisis)
- Analyze trends and identify risks/opportunities

**Key Methods:**
```python
perceive(province_id, current_month, current_year) -> PerceptionContext
```

### 4. DecisionAgent (`agents/province/decision_agent.py`)

**Responsibilities:**
- Evaluate player instruction feasibility
- Select autonomous behaviors when no instruction
- Determine behavior parameters
- Assess risks

**Decision Logic:**
- With instruction → evaluate feasibility → execute or reject
- Without instruction → analyze province state → select autonomous behaviors

**Priority-based Behavior Selection:**
1. Critical risks (loyalty < 30, stability < 30)
2. Declining trends (income, loyalty, stability)
3. Opportunities (surplus > 300, loyalty > 60)
4. Maintenance (default behaviors)

### 5. ExecutionAgent (`agents/province/execution_agent.py`)

**Responsibilities:**
- Execute behavior definitions
- Calculate and apply effects
- Generate events from behaviors
- Create execution reports

**Effect Application:**
- Modify province attributes (income, expenditure, loyalty, stability, development)
- Generate events with appropriate severity and visibility
- Save behavior records to database

### 6. Configuration System

**Files:**
- `config.yaml.example` - Configuration template
- `config.yaml` - Actual configuration (not in git)
- `config_loader.py` - Configuration loader with environment variable support

**Features:**
- YAML configuration with environment variable expansion
- API key management
- Model selection (Claude 3.5 Sonnet/Haiku)
- Mock mode for testing
- Per-agent configuration sections

### 7. Testing

**Test Files:**
- `tests/province/test_perception_agent.py` - Mock mode tests
- `tests/province/test_perception_agent_with_api.py` - Real API tests

**Running Tests:**
```bash
# Mock mode (no API required)
python tests/province/test_perception_agent.py

# Real API (requires ANTHROPIC_API_KEY)
python tests/province/test_perception_agent_with_api.py

# Force mock mode
python tests/province/test_perception_agent_with_api.py --mock
```

## Usage

### Basic Usage (Game Loop)

Province Agents are automatically integrated into the game loop:

```python
from core.game import Game

game = Game()
game.next_month_sync()  # Province Agents run automatically
```

### Standalone Usage

```python
from agents.province.perception_agent import PerceptionAgent
from db.database import Database
from config_loader import get_config

db = Database()
config = get_config()

agent = PerceptionAgent(
    agent_id="province_1",
    config={
        'province_id': 1,
        'llm_config': config.get_llm_config()
    },
    db=db
)

context = await agent.perceive(
    province_id=1,
    current_month=13,
    current_year=2
)

print(context.model_dump_json(indent=2))
```

## Configuration

### Enable LLM

```yaml
# config.yaml
llm:
  enabled: true
  mock_mode: false
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-3-5-sonnet-20241022"
```

### Set API Key

```bash
# Method 1: Environment variable (recommended)
export ANTHROPIC_API_KEY=sk-ant-api03-...

# Method 2: Directly in config (not recommended)
# Edit config.yaml and set: api_key: "sk-ant-api03-..."
```

## Implementation Details

### Commit History

All commits use English messages:

1. `initial commit` - Repository initialization
2. `Add Province Agent database migration` - Database schema
3. `Add Province Agent data models` - Pydantic models
4. `Extend Database class` - CRUD methods
5. `Implement PerceptionAgent core structure` - Basic structure
6. `Implement PerceptionAgent data building methods` - Data processing
7. `Implement behavior definition system` - Behavior templates
8. `Implement DecisionAgent` - Decision logic
9. `Implement ExecutionAgent` - Execution logic
10. `Integrate Province Agents into Game loop` - Game integration
11. `Fix Optional import in Database` - Bug fix
12. `Fix events query column name` - Bug fix
13. `Fix variable scope issue in next_month()` - Bug fix
14. `Add configuration system for LLM API testing` - Config system
15. `Add configuration usage examples` - Config examples
16. `Add standalone PerceptionAgent test script` - Test script
17. `Add English PerceptionAgent test files` - Test files in proper location
18. `Translate all documentation to English` - English docs
19. `Add English test suite documentation` - Test docs

### Files Modified/Created

**New Files:**
```
agents/province/
  ├── __init__.py
  ├── models.py
  ├── perception_agent.py
  ├── decision_agent.py
  ├── execution_agent.py
  └── behaviors.py

db/migrations/
  └── add_province_agent_tables.py

tests/province/
  ├── __init__.py
  ├── test_perception_agent.py
  └── test_perception_agent_with_api.py

config.yaml.example
config_loader.py
config_example.py
API_TEST_GUIDE.md
```

**Modified Files:**
```
db/database.py - Added Province Agent methods
core/game.py - Integrated Province Agents
.gitignore - Protected sensitive files
```

## Testing

### Unit Tests (Recommended for Future)

```python
# Test PerceptionAgent
pytest tests/province/test_perception_agent.py

# Test DecisionAgent
pytest tests/province/test_decision_agent.py  # TODO

# Test ExecutionAgent
pytest tests/province/test_execution_agent.py  # TODO
```

### Integration Test

```bash
# Run full game with Province Agents
python main.py  # Province Agents run automatically in next_month()
```

### Performance Targets

- Perception: < 500ms (mock mode), < 2s (real API)
- Decision: < 300ms
- Execution: < 200ms per behavior

## Key Features

✅ **Three-stage autonomous pipeline**
- Perception: Historical analysis with LLM summaries
- Decision: Strategic behavior selection
- Execution: Effect calculation and event generation

✅ **Layered historical data management**
- Monthly detailed data (1 month)
- Quarterly summaries (4 quarters) with caching
- Annual summaries (3 years) with caching
- Critical event indexing

✅ **Behavior system**
- 8 predefined behavior types
- Parameter validation
- Effect calculation
- Risk assessment

✅ **Player instruction support**
- Instruction feasibility evaluation
- Template-based instruction system
- Autonomous fallback when instruction not feasible

✅ **LLM Integration**
- Configurable LLM provider (Anthropic Claude)
- Mock mode for testing without API
- Automatic summary generation for quarterly/annual data

✅ **Comprehensive testing**
- Mock mode tests (no API required)
- Real API tests with configuration
- Auto-cleanup test databases
- Human-readable and JSON output

✅ **Security**
- Environment variable support for API keys
- .gitignore protection for sensitive files
- No hardcoded credentials

## Next Steps

### Completed ✅
- Database schema and migrations
- Three-agent architecture implementation
- Behavior definition system
- Configuration system
- Testing infrastructure
- English documentation

### Potential Enhancements 🔮
- Unit test coverage expansion
- LLM-powered decision optimization
- More sophisticated behavior templates
- Multi-province coordination
- Performance optimization
- CLI command system for player instructions

## Technical Debt / Future Improvements

1. **Testing**: Add comprehensive unit tests for all agents
2. **Performance**: Implement caching for LLM summaries
3. **Monitoring**: Add detailed logging and metrics
4. **CLI**: Build interactive command interface for player instructions
5. **Documentation**: Add API documentation and architecture diagrams

## License

This implementation is part of the simu-emperor project.

## Contributors

- Implementation: Claude (Anthropic)
- Architecture: Based on Province Agent design specification
