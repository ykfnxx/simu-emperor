"""Standard tools built into the SDK — only communication primitives.

Per design, the SDK ships exactly two standard tools:
  1. send_message — send a message to other agents or the player
  2. query_state — query game state from the Server
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from simu_sdk.tools.registry import tool

if TYPE_CHECKING:
    from simu_shared.models import TapeEvent

    from simu_sdk.client import ServerClient


class StandardTools:
    """Minimal communication tool set.

    Requires a ``ServerClient`` instance injected at construction time.
    """

    def __init__(self, server: ServerClient) -> None:
        self._server = server

    @tool(
        name="send_message",
        description="Send a message to other agents or the player.",
        parameters={
            "recipients": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Target agent IDs or 'player'.",
            },
            "message": {
                "type": "string",
                "description": "Message content.",
            },
        },
        category="communication",
    )
    async def send_message(self, args: dict, event: TapeEvent) -> str:
        await self._server.post_message(
            recipients=args["recipients"],
            message=args["message"],
            session_id=event.session_id,
        )
        return "Message sent."

    @tool(
        name="query_state",
        description="Query game state from the Server.",
        parameters={
            "path": {
                "type": "string",
                "description": "State path, e.g. 'imperial_treasury', 'provinces.zhili'.",
            },
        },
        category="communication",
    )
    async def query_state(self, args: dict, event: TapeEvent) -> str:
        import json

        result = await self._server.query_state(path=args.get("path", ""))
        return json.dumps(result, ensure_ascii=False, default=str)
