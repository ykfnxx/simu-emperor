"""
Configuration loader for Province Agent system

Supports loading configuration from YAML files and environment variables.
"""

import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path


class Config:
    """Configuration class for Province Agent system"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration

        Args:
            config_path: Path to config file (default: config.yaml)
        """
        self.config_path = config_path or "config.yaml"
        self.config: Dict[str, Any] = {}

        # Try to load config
        if os.path.exists(self.config_path):
            self.load()
        else:
            # Use default config
            self.config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'llm': {
                'enabled': False,
                'provider': 'anthropic',  # anthropic, openai, custom
                'api_key': None,
                'base_url': None,  # For custom API endpoints
                'model': 'claude-3-5-sonnet-20241022',
                'max_tokens': 4096,
                'temperature': 0.3,
                'mock_mode': True
            },
            'province_agent': {
                'enabled': True,
                'mode': 'rule_based',
                'behavior': {
                    'auto_execute': True,
                    'max_behaviors': 3,
                    'risk_threshold': 'medium'
                }
            },
            'perception_agent': {
                'history': {
                    'monthly_months': 1,
                    'quarterly_quarters': 4,
                    'annual_years': 3
                },
                'critical_events': {
                    'categories': ['rebellion', 'war', 'disaster', 'crisis'],
                    'max_events': 8
                },
                'summary': {
                    'use_llm': False,
                    'max_length': 100
                }
            },
            'decision_agent': {
                'instruction': {
                    'allow_instructions': True,
                    'timeout_months': 3
                },
                'autonomous': {
                    'enabled': True,
                    'strategy': 'balanced'
                }
            },
            'execution_agent': {
                'execution': {
                    'validate_params': True,
                    'generate_events': True
                },
                'events': {
                    'default_visibility': 'provincial',
                    'log_history': True
                }
            },
            'logging': {
                'level': 'INFO',
                'verbose': True,
                'file': 'province_agent.log',
                'console': True
            },
            'database': {
                'path': 'game.db',
                'wal_mode': True,
                'pool_size': 5
            },
            'testing': {
                'use_test_db': False,
                'test_db_path': 'test_province_agent.db',
                'cleanup_after_test': True
            }
        }

    def load(self) -> None:
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)

            # Expand environment variables
            self._expand_env_vars()

        except Exception as e:
            print(f"Warning: Failed to load config from {self.config_path}: {e}")
            print("Using default configuration")
            self.config = self._get_default_config()

    def save(self, path: Optional[str] = None) -> None:
        """Save configuration to file"""
        save_path = path or self.config_path

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.config, f, default_flow_style=False, allow_unicode=True)

            print(f"Configuration saved to {save_path}")

        except Exception as e:
            print(f"Error saving configuration: {e}")

    def _expand_env_vars(self) -> None:
        """Expand environment variables in configuration"""
        def _expand_value(value: Any) -> Any:
            if isinstance(value, str):
                # Support ${VAR_NAME} format
                if value.startswith('${') and value.endswith('}'):
                    env_var = value[2:-1]
                    return os.getenv(env_var, value)
                return value
            elif isinstance(value, dict):
                return {k: _expand_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [_expand_value(item) for item in value]
            return value

        self.config = _expand_value(self.config)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated key

        Args:
            key: Dot-separated key (e.g., 'llm.enabled')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value by dot-separated key

        Args:
            key: Dot-separated key (e.g., 'llm.enabled')
            value: Value to set
        """
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def get_llm_config(self) -> Dict[str, Any]:
        """Get LLM configuration for agents"""
        return {
            'enabled': self.get('llm.enabled', False),
            'provider': self.get('llm.provider', 'anthropic'),
            'api_key': self.get('llm.api_key'),
            'base_url': self.get('llm.base_url'),
            'model': self.get('llm.model', 'claude-3-5-sonnet-20241022'),
            'max_tokens': self.get('llm.max_tokens', 4096),
            'temperature': self.get('llm.temperature', 0.3),
            'mock_mode': self.get('llm.mock_mode', True)
        }

    def get_province_agent_config(self, province_id: int) -> Dict[str, Any]:
        """Get province agent configuration"""
        return {
            'province_id': province_id,
            'llm_config': self.get_llm_config(),
            'mode': self.get('province_agent.mode', 'rule_based')
        }

    def get_perception_config(self) -> Dict[str, Any]:
        """Get perception agent configuration"""
        return {
            'history_months': self.get('perception_agent.history.monthly_months', 1),
            'quarterly_quarters': self.get('perception_agent.history.quarterly_quarters', 4),
            'annual_years': self.get('perception_agent.history.annual_years', 3),
            'critical_categories': self.get('perception_agent.critical_events.categories', ['rebellion', 'war', 'disaster']),
            'max_critical_events': self.get('perception_agent.critical_events.max_events', 8),
            'use_llm_summary': self.get('perception_agent.summary.use_llm', False)
        }

    def get_decision_config(self) -> Dict[str, Any]:
        """Get decision agent configuration"""
        return {
            'allow_instructions': self.get('decision_agent.instruction.allow_instructions', True),
            'autonomous_enabled': self.get('decision_agent.autonomous.enabled', True),
            'strategy': self.get('decision_agent.autonomous.strategy', 'balanced')
        }

    def get_execution_config(self) -> Dict[str, Any]:
        """Get execution agent configuration"""
        return {
            'validate_params': self.get('execution_agent.execution.validate_params', True),
            'generate_events': self.get('execution_agent.execution.generate_events', True),
            'default_visibility': self.get('execution_agent.events.default_visibility', 'provincial'),
            'log_history': self.get('execution_agent.events.log_history', True)
        }

    def is_llm_enabled(self) -> bool:
        """Check if LLM is enabled"""
        enabled = self.get('llm.enabled', False)
        has_key = bool(self.get('llm.api_key'))
        not_mock = not self.get('llm.mock_mode', True)

        return enabled and has_key and not_mock

    def __repr__(self) -> str:
        return f"Config(path={self.config_path}, llm_enabled={self.is_llm_enabled()})"


# Global config instance
_global_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get global configuration instance

    Args:
        config_path: Optional path to config file

    Returns:
        Config instance
    """
    global _global_config

    if _global_config is None:
        _global_config = Config(config_path)

    return _global_config


def init_config(config_path: Optional[str] = None) -> Config:
    """
    Initialize global configuration

    Args:
        config_path: Optional path to config file

    Returns:
        Config instance
    """
    global _global_config

    _global_config = Config(config_path)

    return _global_config


# CLI helper
def setup_config_from_args():
    """
    Setup configuration from command line arguments

    Usage:
        python your_script.py --config config.yaml --api-key your-key
    """
    import sys

    config_path = "config.yaml"
    api_key = None

    # Parse command line args
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == '--config' and i + 1 < len(args):
            config_path = args[i + 1]
        elif arg == '--api-key' and i + 1 < len(args):
            api_key = args[i + 1]
        elif arg.startswith('--api-key='):
            api_key = arg.split('=', 1)[1]

    # Override API key if provided
    if api_key:
        os.environ['ANTHROPIC_API_KEY'] = api_key

    # Load config
    config = init_config(config_path)

    # Check if LLM is properly configured
    if config.is_llm_enabled():
        print(f"✓ LLM enabled: {config.get('llm.model')}")
    else:
        print("ℹ LLM disabled or not configured (using mock mode)")
        if not config.get('llm.api_key'):
            print("  Set ANTHROPIC_API_KEY environment variable or add to config.yaml")

    return config


if __name__ == "__main__":
    # Test configuration loading
    print("Testing configuration loader...")

    config = setup_config_from_args()

    print("\n" + "="*60)
    print("Configuration Summary")
    print("="*60)
    print(f"Config file: {config.config_path}")
    print(f"LLM enabled: {config.is_llm_enabled()}")
    print(f"LLM model: {config.get('llm.model')}")
    print(f"LLM mock mode: {config.get('llm.mock_mode')}")
    print(f"Province Agent enabled: {config.get('province_agent.enabled')}")
    print(f"Database path: {config.get('database.path')}")
