
from abc import ABC, abstractmethod
from typing import Sequence

import numpy as np
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.exceptions import EmbeddingError
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingProvider(ABC):
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        pass
    
    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        pass
    
    async def embed_text(self, text: str) -> list[float]:
        embeddings = await self.embed_texts([text])
        return embeddings[0]


class OpenAIEmbeddings(EmbeddingProvider):
    
    # Model dimensions
    MODEL_DIMENSIONS = {
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
        "text-embedding-ada-002": 1536,
    }
    
    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model = model or settings.embedding_model
        self.api_key = api_key or settings.openai_api_key
        
        if not self.api_key:
            raise EmbeddingError("OpenAI API key not configured")
        
        # Lazy import to avoid dependency if not used
        from openai import AsyncOpenAI
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        logger.info(
            "OpenAI embeddings initialized",
            model=self.model,
        )
    
    @property
    def dimension(self) -> int:
        return self.MODEL_DIMENSIONS.get(self.model, settings.embedding_dimension)
    
    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        # Preprocess texts
        processed_texts = [self._preprocess_text(t) for t in texts]
        
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=processed_texts,
            )
            
            # Extract embeddings in order
            embeddings = [item.embedding for item in response.data]
            
            logger.debug(
                "Generated embeddings",
                count=len(texts),
                model=self.model,
            )
            
            return embeddings
            
        except Exception as e:
            logger.error(
                "Embedding generation failed",
                error=str(e),
                model=self.model,
            )
            raise EmbeddingError(f"Failed to generate embeddings: {str(e)}")
    
    def _preprocess_text(self, text: str) -> str:
        # Truncate to avoid token limits (8192 for most models)
        # Using character limit as approximation
        max_chars = 30000  # ~8000 tokens
        if len(text) > max_chars:
            text = text[:max_chars]
        
        # Normalize whitespace
        text = " ".join(text.split())
        
        return text


class SentenceTransformerEmbeddings(EmbeddingProvider):
    
    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        self.model_name = model or "all-MiniLM-L6-v2"
        
        try:
            from sentence_transformers import SentenceTransformer
            
            logger.info(
                "Loading sentence transformer model",
                model=self.model_name,
            )
            
            self.model = SentenceTransformer(self.model_name)
            self._dimension = self.model.get_sentence_embedding_dimension()
            
            logger.info(
                "Sentence transformer loaded",
                model=self.model_name,
                dimension=self._dimension,
            )
            
        except ImportError:
            raise EmbeddingError(
                "sentence-transformers library not installed. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            raise EmbeddingError(f"Failed to load model: {str(e)}")
    
    @property
    def dimension(self) -> int:
        return self._dimension
    
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        
        try:
            # Sentence transformers is synchronous, but we keep async interface
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,  # L2 normalization
            )
            
            # Convert to list of lists
            embeddings_list = embeddings.tolist()
            
            logger.debug(
                "Generated local embeddings",
                count=len(texts),
                model=self.model_name,
            )
            
            return embeddings_list
            
        except Exception as e:
            logger.error(
                "Local embedding generation failed",
                error=str(e),
            )
            raise EmbeddingError(f"Failed to generate embeddings: {str(e)}")


class EmbeddingService:
    
    # Maximum texts per batch (provider dependent)
    MAX_BATCH_SIZE = 100
    
    def __init__(
        self,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        if provider:
            self.provider = provider
        elif settings.embedding_provider == "openai":
            self.provider = OpenAIEmbeddings()
        else:
            self.provider = SentenceTransformerEmbeddings(
                model=settings.embedding_model
            )
        
        # Simple in-memory cache
        # In production, consider Redis or similar
        self._cache: dict[str, list[float]] = {}
    
    @property
    def dimension(self) -> int:
        return self.provider.dimension
    
    async def embed_text(self, text: str, use_cache: bool = True) -> list[float]:
        if use_cache:
            cache_key = self._cache_key(text)
            if cache_key in self._cache:
                logger.debug("Embedding cache hit")
                return self._cache[cache_key]
        
        embedding = await self.provider.embed_text(text)
        
        if use_cache:
            self._cache[cache_key] = embedding
        
        return embedding
    
    async def embed_texts(
        self,
        texts: list[str],
        use_cache: bool = True,
        show_progress: bool = False,
    ) -> list[list[float]]:
        if not texts:
            return []
        
        # Check cache for each text
        results: list[list[float] | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []
        
        if use_cache:
            for i, text in enumerate(texts):
                cache_key = self._cache_key(text)
                if cache_key in self._cache:
                    results[i] = self._cache[cache_key]
                else:
                    texts_to_embed.append((i, text))
        else:
            texts_to_embed = list(enumerate(texts))
        
        # Embed uncached texts in batches
        if texts_to_embed:
            for batch_start in range(0, len(texts_to_embed), self.MAX_BATCH_SIZE):
                batch = texts_to_embed[batch_start:batch_start + self.MAX_BATCH_SIZE]
                batch_indices = [idx for idx, _ in batch]
                batch_texts = [text for _, text in batch]
                
                batch_embeddings = await self.provider.embed_texts(batch_texts)
                
                for idx, text, embedding in zip(batch_indices, batch_texts, batch_embeddings):
                    results[idx] = embedding
                    if use_cache:
                        self._cache[self._cache_key(text)] = embedding
                
                if show_progress:
                    logger.info(
                        "Embedding progress",
                        completed=batch_start + len(batch),
                        total=len(texts_to_embed),
                    )
        
        # All results should be filled now
        return [r for r in results if r is not None]
    
    def _cache_key(self, text: str) -> str:
        # Use hash of text for cache key
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()
    
    def clear_cache(self) -> None:
        self._cache.clear()
        logger.info("Embedding cache cleared")


# Singleton instance for dependency injection
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
