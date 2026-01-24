"""
Agent Base Class - Provides LLM calling infrastructure
Implements structured LLM calling using Pydantic + Instructor
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, TypeVar
from pydantic import BaseModel
import instructor
import anthropic
import enum

T = TypeVar('T', bound=BaseModel)


class LLMProvider(str, enum.Enum):
    """LLM Service Provider"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    CUSTOM = "custom"  # For custom OpenAI-compatible APIs


class LLMConfig(BaseModel):
    """LLM Configuration"""
    enabled: bool = False
    provider: LLMProvider = LLMProvider.ANTHROPIC
    model: str = "claude-3-haiku-20240307"
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # Custom API endpoint URL
    mock_mode: bool = True  # Default to mock mode to avoid API dependency
    max_tokens: int = 1024
    temperature: float = 0.1


class AgentMode(enum.Enum):
    """Agent Operation Mode"""
    RULE_BASED = "rule_based"  # Pure rule-driven
    LLM_ASSISTED = "llm_assisted"  # LLM-assisted decision making


class BaseAgent(ABC):
    """Agent Abstract Base Class, provides LLM calling infrastructure"""

    def __init__(self, agent_id: str, config: Dict[str, Any]):
        """Initialize Agent

        Args:
            agent_id: Agent unique identifier
            config: Configuration dictionary containing llm_config etc.
        """
        self.agent_id = agent_id
        self.llm_config = LLMConfig(**config.get('llm_config', {}))
        self.mode = AgentMode(config.get('mode', 'rule_based'))

        # Initialize LLM client (only when enabled)
        self._client = None
        if self.llm_config.enabled and not self.llm_config.mock_mode:
            if self.llm_config.api_key:
                self._client = self._init_llm_client()
            else:
                # If trying to enable LLM but no API key, keep as None and fall back to mock
                self.llm_config.mock_mode = True

    def _init_llm_client(self):
        """Initialize LLM client based on provider configuration"""
        try:
            if self.llm_config.provider == LLMProvider.ANTHROPIC:
                # Use Anthropic API
                return instructor.from_anthropic(
                    anthropic.Anthropic(api_key=self.llm_config.api_key)
                )

            elif self.llm_config.provider in [LLMProvider.OPENAI, LLMProvider.CUSTOM]:
                # Use OpenAI-compatible API (including custom endpoints)
                import openai

                if self.llm_config.base_url:
                    # Custom endpoint (e.g., local models, proxies)
                    client = openai.OpenAI(
                        api_key=self.llm_config.api_key or "dummy-key",
                        base_url=self.llm_config.base_url
                    )
                else:
                    # Official OpenAI API
                    client = openai.OpenAI(api_key=self.llm_config.api_key)

                return instructor.from_openai(client)

            else:
                print(f"Warning: Unknown LLM provider '{self.llm_config.provider}', falling back to mock mode")
                self.llm_config.mock_mode = True
                return None

        except ImportError as e:
            print(f"Warning: Failed to import required library for {self.llm_config.provider.value}: {e}")
            print(f"Please install required packages:")
            if self.llm_config.provider == LLMProvider.OPENAI:
                print("  pip install openai")
            self.llm_config.mock_mode = True
            return None
        except Exception as e:
            print(f"Warning: Failed to initialize LLM client: {e}")
            self.llm_config.mock_mode = True
            return None

    async def call_llm_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None
    ) -> Optional[T]:
        """Call LLM and return structured data

        Args:
            prompt: User prompt
            response_model: Pydantic model type for structured output
            system_prompt: System prompt (optional)

        Returns:
            Structured data (Pydantic model instance), returns None on failure
        """
        # If LLM not enabled or in mock mode, use mock response
        if not self.llm_config.enabled or self.llm_config.mock_mode:
            return await self._mock_llm_response(response_model)

        # If no valid LLM client (e.g., missing API key), use mock
        if not self._client:
            print(f"Warning: Agent {self.agent_id} LLM call unavailable, falling back to mock mode")
            return await self._mock_llm_response(response_model)

        try:
            # Use instructor to call LLM, automatically parse to structured data
            response = self._client.messages.create(
                model=self.llm_config.model,
                max_tokens=self.llm_config.max_tokens,
                temperature=self.llm_config.temperature,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt or "You are a helpful assistant."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_model=response_model
            )
            return response

        except Exception as e:
            print(f"LLM call failed ({self.agent_id}): {str(e)}")
            return await self._mock_llm_response(response_model)

    async def call_llm_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Optional[str]:
        """Call LLM and return text response

        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)

        Returns:
            Text response, returns None on failure
        """
        # If LLM not enabled or in mock mode, use mock text response
        if not self.llm_config.enabled or self.llm_config.mock_mode:
            return await self._mock_llm_text_response(prompt)

        if not self._client:
            print(f"Warning: Agent {self.agent_id} LLM call unavailable, falling back to mock mode")
            return await self._mock_llm_text_response(prompt)

        try:
            messages = [
                {
                    "role": "system",
                    "content": system_prompt or "You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]

            # Use different API call based on provider
            if self.llm_config.provider == LLMProvider.ANTHROPIC:
                # Anthropic API
                response = self._client.messages.create(
                    model=self.llm_config.model,
                    max_tokens=self.llm_config.max_tokens,
                    temperature=self.llm_config.temperature,
                    messages=messages
                )
                return response.content[0].text

            elif self.llm_config.provider in [LLMProvider.OPENAI, LLMProvider.CUSTOM]:
                # OpenAI-compatible API
                # Note: When using instructor, we need to access the underlying client
                import openai
                if hasattr(self._client, 'client'):
                    # Instructor wrapper
                    underlying_client = self._client.client
                else:
                    # Direct client
                    underlying_client = self._client

                response = underlying_client.chat.completions.create(
                    model=self.llm_config.model,
                    max_tokens=self.llm_config.max_tokens,
                    temperature=self.llm_config.temperature,
                    messages=messages
                )
                return response.choices[0].message.content

            else:
                print(f"Warning: Unknown provider '{self.llm_config.provider}', falling back to mock mode")
                return await self._mock_llm_text_response(prompt)

        except Exception as e:
            print(f"LLM call failed ({self.agent_id}): {str(e)}")
            return await self._mock_llm_text_response(prompt)

    @abstractmethod
    async def _mock_llm_response(self, response_model: Type[T]) -> T:
        """Generate mock LLM response (subclass implementation)

        Args:
            response_model: Expected response model type

        Returns:
            Mock Pydantic model instance
        """
        pass

    @abstractmethod
    async def _mock_llm_text_response(self, prompt: str) -> str:
        """Generate mock text response (subclass implementation)

        Args:
            prompt: User prompt

        Returns:
            Mock text response
        """
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize Agent (subclass implementation)

        Args:
            config: Configuration dictionary
        """
        pass

    @abstractmethod
    async def on_month_start(self, game_state: Dict[str, Any],
                           provinces: List[Dict[str, Any]]) -> None:
        """Called at month start (subclass implementation)

        Args:
            game_state: Game state
            provinces: Province list
        """
        pass

    @abstractmethod
    async def take_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Execute action and return result (subclass implementation)

        Args:
            context: Execution context

        Returns:
            Action result dictionary, or None
        """
        pass

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """Get Agent current state (subclass implementation)

        Returns:
            State dictionary
        """
        pass
