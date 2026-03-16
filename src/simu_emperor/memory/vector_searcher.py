"""VectorSearcher for semantic memory retrieval using ChromaDB."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from simu_emperor.memory.models import TapeSegment

if TYPE_CHECKING:
    from simu_emperor.config import EmbeddingConfig

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.utils import embedding_functions

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("chromadb not installed. VectorSearcher requires: uv add chromadb")


class VectorSearcher:
    """
    Vector-based semantic memory searcher using ChromaDB.

    Uses ChromaDB's built-in OpenAIEmbeddingFunction for embeddings.
    """

    def __init__(self, memory_dir: Path, config: "EmbeddingConfig"):
        """
        Initialize VectorSearcher.

        Args:
            memory_dir: Base memory directory path
            config: EmbeddingConfig instance
        """
        if not CHROMADB_AVAILABLE:
            raise ImportError("chromadb is required. Install with: uv add chromadb")

        self.memory_dir = memory_dir
        self.config = config

        # Create embedding function based on provider
        if config.provider == "openai":
            if not config.api_key:
                raise ValueError("OpenAI API key is required when provider is 'openai'")
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=config.api_key,
                model_name=config.model,
            )
        elif config.provider == "mock":
            self.embedding_fn = _MockEmbeddingFunction(dimension=1536)
        else:
            raise ValueError(f"Unsupported provider: {config.provider}")

        # Initialize ChromaDB client and collection
        db_path = memory_dir / "chroma_db"
        self.client = chromadb.PersistentClient(path=str(db_path))
        self.collection = self.client.get_or_create_collection(
            name="segments",
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(f"VectorSearcher initialized with provider={config.provider}, db_path={db_path}")

    async def add_segments(self, segments: list[TapeSegment]) -> None:
        """
        Add segments to vector store.

        Args:
            segments: List of TapeSegment to add
        """
        if not segments:
            return

        documents = [self._segment_to_text(s) for s in segments]
        metadatas = [
            {
                "session_id": s.session_id,
                "agent_id": s.agent_id,
                "tick_start": s.tick_start,
                "tick_end": s.tick_end,
            }
            for s in segments
        ]
        ids = [self._make_id(s) for s in segments]

        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )

        logger.debug(f"Added {len(segments)} segments to vector store")

    async def search(
        self,
        query: str,
        agent_id: str,
        n_results: int = 5,
    ) -> list[str]:
        """
        Search for similar segments by query text.

        Args:
            query: Query text
            agent_id: Agent identifier for filtering
            n_results: Maximum number of results to return

        Returns:
            List of segment IDs, ordered by relevance
        """
        if not query:
            return []

        results = self.collection.query(
            query_texts=[query],
            where={"agent_id": agent_id},
            n_results=n_results,
        )

        segment_ids = results["ids"][0] if results.get("ids") else []
        logger.debug(f"Vector search returned {len(segment_ids)} results for query: {query[:50]}...")

        return segment_ids

    def _segment_to_text(self, segment: TapeSegment) -> str:
        """
        Convert segment to text for embedding.

        Args:
            segment: TapeSegment to convert

        Returns:
            Text representation
        """
        parts = []

        for event in segment.events:
            # Extract text from payload or content
            payload = event.get("payload") or event.get("content", {})

            if isinstance(payload, dict):
                query = payload.get("query", "")
                intent = payload.get("intent", "")
                response = payload.get("response", "")

                if query:
                    parts.append(query)
                if intent:
                    parts.append(intent)
                if response:
                    parts.append(response)
            elif isinstance(payload, str):
                parts.append(payload)

            # Also include event type
            event_type = event.get("type") or event.get("event_type", "")
            if event_type:
                parts.append(event_type)

        return " ".join(parts)

    def _make_id(self, segment: TapeSegment) -> str:
        """
        Generate unique ID for a segment.

        Args:
            segment: TapeSegment

        Returns:
            Unique ID string
        """
        return f"{segment.session_id}:{segment.start_position}:{segment.end_position}"


class _MockEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """Mock embedding function for testing."""

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        # Fixed seed for reproducibility
        import random

        self._random = random.Random(42)

    def __call__(self, input_texts):
        """Generate mock embeddings."""
        return [
            [self._random.random() for _ in range(self.dimension)] for _ in input_texts
        ]
