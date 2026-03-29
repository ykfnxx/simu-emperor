import logging
from typing import Any

from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, client: SeekDBClient):
        self._client = client

    async def generate_embedding(self, text: str) -> bytes:
        raise NotImplementedError("Embedding generation requires LLM provider integration")

    async def store_embedding(self, segment_id: int, embedding: bytes) -> None:
        await self._client.execute(
            "UPDATE tape_segments SET embedding = ? WHERE id = ?", embedding, segment_id
        )
