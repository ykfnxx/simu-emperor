# Province Agent API Testing Guide

## Configuration System Description

### File Structure

```
/Users/yangkefan/workspace/simu-emperor/
├── config.yaml.example           # Configuration template (committed to git)
├── config.yaml                   # Actual configuration file (not committed)
├── config_loader.py              # Configuration loading module
├── tests/province/test_perception_agent_with_api.py   # API test script
└── .gitignore                    # Protect sensitive information
```

### Quick Start

#### 1. Create Configuration File

```bash
# Copy configuration template
cp config.yaml.example config.yaml

# Edit configuration file
vim config.yaml  # or use your preferred editor
```

#### 2. Configure API Key

There are two ways to set the API key:

**Method 1: Directly in config.yaml**
```yaml
llm:
  api_key: "sk-ant-api03-..."  # Your Anthropic API key
```

**Method 2: Use environment variable (recommended)**
```bash
# Set in terminal
export ANTHROPIC_API_KEY=sk-ant-api03-...

# Or add to ~/.bashrc or ~/.zshrc
echo 'export ANTHROPIC_API_KEY=sk-ant-api03-...' >> ~/.bashrc
source ~/.bashrc
```

Then use in config.yaml:
```yaml
llm:
  api_key: "${ANTHROPIC_API_KEY}"
```

#### 3. Enable LLM

Edit config.yaml:
```yaml
llm:
  enabled: true        # Enable LLM
  mock_mode: false     # Disable mock mode
  model: "claude-3-5-sonnet-20241022"  # Select model
```

#### 4. Run Tests

```bash
# Use settings from config file
python tests/province/test_perception_agent_with_api.py

# Or directly specify API key (overrides config file)
python tests/province/test_perception_agent_with_api.py --api-key sk-ant-api03-...

# Force mock mode (no API calls)
python tests/province/test_perception_agent_with_api.py --mock
```

## Configuration Options

### LLM Configuration

```yaml
llm:
  enabled: true                          # Enable LLM
  api_key: "${ANTHROPIC_API_KEY}"        # API key
  model: "claude-3-5-sonnet-20241022"   # Model selection
  max_tokens: 4096                       # Max tokens
  temperature: 0.3                       # Temperature (0-1)
  mock_mode: false                       # Mock mode
```

**Available models:**
- `claude-3-5-sonnet-20241022` - Strongest, slower, more expensive
- `claude-3-5-haiku-20241022` - Fast, inexpensive, good for testing
- `claude-3-opus-20240229` - Previous strongest model
- `claude-3-haiku-20240307` - Previous fast model

### Province Agent Configuration

```yaml
province_agent:
  enabled: true              # Enable Province Agent system
  mode: "llm_assisted"       # Operation mode
  behavior:
    auto_execute: true       # Auto-execute behaviors
    max_behaviors: 3         # Max parallel behaviors
    risk_threshold: "medium"  # Risk threshold
```

**Operation modes:**
- `rule_based` - Pure rule-driven (fastest)
- `llm_assisted` - LLM-assisted decision making (requires API)

### PerceptionAgent Configuration

```yaml
perception_agent:
  history:
    monthly_months: 1        # Monthly detailed data months
    quarterly_quarters: 4    # Quarterly summary quarters
    annual_years: 3          # Annual summary years

  critical_events:
    categories:              # Critical event categories
      - rebellion
      - war
      - disaster
      - crisis
    max_events: 8            # Max indexed events

  summary:
    use_llm: true            # Use LLM to generate summaries
    max_length: 100          # Summary length limit
```

## Test Script Description

### tests/province/test_perception_agent_with_api.py

Test PerceptionAgent with real LLM API.

**Features:**
- Generate 12 months of test data
- Run PerceptionAgent analysis
- Call LLM to generate quarterly and annual summaries
- Output trend analysis and risk assessment
- Save full JSON results

**Output:**
- Console: Human-readable result summary
- JSON file: Complete PerceptionContext data

**Command-line arguments:**
```bash
--config <path>      # Specify config file
--api-key <key>      # Directly provide API key
--mock               # Force mock mode
```

## Configuration Loading Examples

### Using in Python Code

```python
from config_loader import get_config, init_config

# Method 1: Use default config file
config = get_config()

# Method 2: Specify config file
config = init_config("my_config.yaml")

# Method 3: Initialize from command line args
from config_loader import setup_config_from_args
config = setup_config_from_args()

# Get configuration values
llm_enabled = config.get('llm.enabled', False)
model = config.get('llm.model', 'claude-3-5-sonnet-20241022')

# Get LLM config (for Agents)
llm_config = config.get_llm_config()

# Get Province Agent config
agent_config = config.get_province_agent_config(province_id=1)

# Check if LLM is enabled
if config.is_llm_enabled():
    print("LLM is enabled and configured")
else:
    print("Using mock mode")

# Modify configuration
config.set('llm.enabled', True)
config.set('llm.temperature', 0.5)

# Save configuration
config.save("new_config.yaml")
```

## Security Best Practices

### 1. Never Commit API Keys

✅ **Correct:**
```yaml
# config.yaml
api_key: "${ANTHROPIC_API_KEY}"  # Read from environment variable
```

```bash
# Set in terminal or script
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

❌ **Wrong:**
```yaml
# config.yaml
api_key: "sk-ant-api03-ABC123..."  # Never write directly
```

### 2. Use Environment Variables

Create `.env` file (already in .gitignore):
```bash
# .env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

Load environment variables:
```python
from dotenv import load_dotenv
load_dotenv()  # Auto-load .env file
```

### 3. Limit API Key Permissions

- Create dedicated API key for testing
- Set spending limit
- Rotate API key regularly

### 4. Log Security

Configured .gitignore to ignore:
- `config.yaml` - Configuration file with API keys
- `*.log` - Log files may contain sensitive data
- `test_*.db` - Test databases

## Common Issues

### Q: How to get API Key?

A: Visit https://console.anthropic.com/ and get one after logging in

### Q: API error during testing?

A: Check:
1. API key is correct
2. Account has balance
3. Model name is correct
4. Network connection is working

### Q: How to switch between mock and real API?

A:
```yaml
# Method 1: Modify configuration file
llm:
  mock_mode: true   # Mock mode
  # mock_mode: false  # Real API

# Method 2: Command line argument
python tests/province/test_perception_agent_with_api.py --mock
```

### Q: How to view API call details?

A: Enable verbose logging:
```yaml
logging:
  level: "DEBUG"
  verbose: true
```

### Q: Approximate testing costs?

A:
- Mock mode: Free
- Haiku model: ~$0.25/1M tokens (recommended for testing)
- Sonnet model: ~$3/1M tokens
- Single test consumes ~1000-2000 tokens, cost ~$0.001-0.01

## Next Steps

1. **Configure API Key**
   ```bash
   export ANTHROPIC_API_KEY=your-key-here
   ```

2. **Enable LLM in config.yaml**
   ```yaml
   llm:
     enabled: true
     mock_mode: false
   ```

3. **Run Tests**
   ```bash
   python tests/province/test_perception_agent_with_api.py
   ```

4. **View Results**
   - Console output
   - `perception_context_api_test.json`

5. **Adjust Configuration**
   - Try different models
   - Adjust temperature
   - Modify history window size

Happy testing! 🚀
