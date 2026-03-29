"""Tests for EmbeddingService."""

import pytest

from simu_emperor.persistence.embedding import EmbeddingService


@pytest.fixture
def embedding_service(mock_client):
    return EmbeddingService(mock_client, provider="mock", dimension=128)


class TestEmbeddingService:
    @pytest.mark.asyncio
    async def test_generate_mock_embedding_returns_bytes(self, embedding_service):
        result = await embedding_service.generate_embedding("test text")
        assert isinstance(result, bytes)
        assert len(result) == 128 * 4

    @pytest.mark.asyncio
    async def test_generate_mock_embedding_is_deterministic(self, embedding_service):
        result1 = await embedding_service.generate_embedding("same text")
        result2 = await embedding_service.generate_embedding("same text")
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_generate_mock_embedding_different_texts(self, embedding_service):
        result1 = await embedding_service.generate_embedding("text one")
        result2 = await embedding_service.generate_embedding("text two")
        assert result1 != result2

    @pytest.mark.asyncio
    async def test_generate_unsupported_provider_raises(self, mock_client):
        service = EmbeddingService(mock_client, provider="unsupported")
        with pytest.raises(ValueError, match="Unsupported embedding provider"):
            await service.generate_embedding("test")

    @pytest.mark.asyncio
    async def test_store_embedding_calls_execute(self, embedding_service, mock_client):
        fake_embedding = b"\x00\x01\x02\x03\x04\x05"

        await embedding_service.store_embedding(segment_id=1, embedding=fake_embedding)

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert "UPDATE tape_segments" in call_args[0]
        assert "embedding = ?" in call_args[0]
        assert fake_embedding in call_args

    @pytest.mark.asyncio
    async def test_store_embedding_with_empty_bytes(self, embedding_service, mock_client):
        await embedding_service.store_embedding(segment_id=2, embedding=b"")

        mock_client.execute.assert_called_once()
        call_args = mock_client.execute.call_args[0]
        assert b"" in call_args
