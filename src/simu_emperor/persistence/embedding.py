import hashlib
import logging
import struct
from typing import Any

from simu_emperor.persistence.client import SeekDBClient


logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, client: SeekDBClient, provider: str = "mock", dimension: int = 1536):
        self._client = client
        self._provider = provider
        self._dimension = dimension

    async def generate_embedding(self, text: str) -> bytes:
        if self._provider == "mock":
            return self._generate_mock_embedding(text)
        if self._provider == "openai":
            return await self._generate_openai_embedding(text)
        raise ValueError(f"Unsupported embedding provider: {self._provider}")

    def _generate_mock_embedding(self, text: str) -> bytes:
        text_hash = hashlib.sha256(f"{text}:{self._dimension}".encode()).digest()
        embedding = []
        for i in range(self._dimension):
            byte_offset = (i * 4) % (len(text_hash) - 4)
            value = struct.unpack("<f", text_hash[byte_offset : byte_offset + 4])[0]
            normalized = (value % 2.0) - 1.0
            embedding.append(normalized)
        return self._float_list_to_bytes(embedding)

    async def _generate_openai_embedding(self, text: str) -> bytes:
        try:
            import openai
        except ImportError:
            raise ImportError(
                "OpenAI package is required for openai embedding provider. Install with: uv add openai"
            )

        client = openai.AsyncOpenAI()
        response = await client.embeddings.create(input=text, model="text-embedding-3-small")
        embedding = response.data[0].embedding
        return self._float_list_to_bytes(embedding)

    def _float_list_to_bytes(self, float_list: list[float]) -> bytes:
        return struct.pack(f"<{len(float_list)}f", *float_list)

    async def store_embedding(self, segment_id: int, embedding: bytes) -> None:
        await self._client.execute(
            "UPDATE tape_segments SET embedding = ? WHERE id = ?", embedding, segment_id
        )
