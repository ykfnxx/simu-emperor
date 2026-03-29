"""QueryParser for natural language query parsing."""

import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simu_emperor.llm.base import LLMProvider

from simu_emperor.memory.models import ParseResult, StructuredQuery
from simu_emperor.memory.exceptions import ParseError


class QueryParser:
    """
    Parses natural language queries into StructuredQuery format.

    Uses LLM with few-shot prompting to extract intent, entities, scope, and depth.
    """

    def __init__(self, llm_provider: "LLMProvider"):
        """
        Initialize QueryParser.

        Args:
            llm_provider: LLM provider for parsing
        """
        self.llm = llm_provider

    async def parse(self, query: str, context: dict = None) -> ParseResult:
        """
        Parse natural language query into StructuredQuery.

        Args:
            query: Natural language query string
            context: Optional context dict

        Returns:
            ParseResult with structured query and metadata

        Raises:
            ParseError: If parsing fails after retries
        """
        start_time = time.time()

        # Try parsing with retries
        for attempt in range(3):
            try:
                response = await self.llm.call(
                    prompt=self._build_prompt(query),
                    system_prompt="你是一个查询解析助手，负责将用户的自然语言查询转换为结构化格式。",
                    temperature=0.1,
                    max_tokens=300,
                    task_type="query_parsing",
                )

                # Parse JSON response
                structured_data = self._extract_json(response)

                # Create StructuredQuery
                structured = StructuredQuery(
                    raw_query=query,
                    intent=structured_data.get("intent", "query_history"),
                    entities=structured_data.get("entities", {}),
                    scope=structured_data.get("scope", "current_session"),
                    depth=structured_data.get("depth", "overview"),
                )

                latency_ms = (time.time() - start_time) * 1000

                return ParseResult(structured=structured, parsed_by="llm", latency_ms=latency_ms)

            except (json.JSONDecodeError, KeyError):
                if attempt == 2:  # Last attempt
                    # Fallback to safe defaults
                    return ParseResult(
                        structured=StructuredQuery(
                            raw_query=query,
                            intent="query_history",
                            entities={},
                            scope="current_session",
                            depth="overview",
                        ),
                        parsed_by="llm_fallback",
                        latency_ms=(time.time() - start_time) * 1000,
                    )
                continue

        raise ParseError(f"Failed to parse query after 3 attempts: {query}")

    def _build_prompt(self, query: str) -> str:
        """
        Build LLM prompt for query parsing.

        Args:
            query: User query

        Returns:
            Prompt string
        """
        return f"""用户查询：{query}

请返回JSON格式的结构化查询：
{{
  "intent": "query_history" | "query_status" | "query_data",
  "entities": {{
    "action": ["拨款", "征税"],
    "target": ["直隶", "江南"],
    "time": "current" | "history"
  }},
  "scope": "current_session" | "cross_session",
  "depth": "overview" | "tape"
}}

示例：
查询："我之前给直隶拨过款吗？"
→ {{"intent": "query_history", "entities": {{"action": ["拨款"], "target": ["直隶"], "time": "history"}}, "scope": "cross_session", "depth": "tape"}}

查询："现在的国库情况？"
→ {{"intent": "query_status", "entities": {{"time": "current"}}, "scope": "current_session", "depth": "overview"}}

只返回JSON，不要其他内容。"""

    def _extract_json(self, response: str) -> dict:
        """
        Extract JSON from LLM response.

        Args:
            response: LLM response string

        Returns:
            Parsed dict

        Raises:
            json.JSONDecodeError: If response is not valid JSON
        """
        # Try direct parse
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                return json.loads(response[start:end].strip())
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                return json.loads(response[start:end].strip())
            else:
                raise
