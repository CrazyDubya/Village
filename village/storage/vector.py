"""Vector storage implementation for semantic memory and RAG."""

import os
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

try:
    from pinecone import Pinecone, ServerlessSpec
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

from village.exceptions import MemoryError as VillageMemoryError


class VectorMemory:
    """Vector storage for semantic search and RAG using Pinecone.

    Attributes:
        api_key: Pinecone API key
        environment: Pinecone environment
        index_name: Name of the Pinecone index
        dimension: Vector dimension (default 1536 for OpenAI embeddings)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        index_name: str = "village-memory",
        dimension: int = 1536,
        metric: str = "cosine",
        **kwargs: Any
    ) -> None:
        """Initialize vector memory storage.

        Args:
            api_key: Pinecone API key (defaults to PINECONE_API_KEY env var)
            environment: Pinecone environment
            index_name: Name of the index to use
            dimension: Vector dimension
            metric: Distance metric (cosine, euclidean, dotproduct)
            **kwargs: Additional Pinecone configuration

        Raises:
            VillageMemoryError: If Pinecone package is not installed
        """
        if not PINECONE_AVAILABLE:
            raise VillageMemoryError(
                "Pinecone package not installed. Install with: pip install pinecone-client>=3.0.0"
            )

        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        if not self.api_key:
            raise VillageMemoryError(
                "Pinecone API key required. Set PINECONE_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.environment = environment or os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
        self.index_name = index_name
        self.dimension = dimension
        self.metric = metric
        self.config = kwargs

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=self.api_key)
        self._index = None

    async def initialize(self) -> None:
        """Initialize the vector index.

        Creates the index if it doesn't exist.

        Raises:
            VillageMemoryError: If initialization fails
        """
        try:
            # Check if index exists
            existing_indexes = self.pc.list_indexes().names()

            if self.index_name not in existing_indexes:
                # Create new index
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.metric,
                    spec=ServerlessSpec(
                        cloud='aws',
                        region='us-east-1'
                    )
                )

            # Connect to index
            self._index = self.pc.Index(self.index_name)

        except Exception as e:
            raise VillageMemoryError(f"Failed to initialize Pinecone index: {str(e)}") from e

    async def store(
        self,
        id: str,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None,
        namespace: str = ""
    ) -> bool:
        """Store a vector with metadata.

        Args:
            id: Unique identifier for the vector
            vector: The embedding vector
            metadata: Associated metadata
            namespace: Optional namespace for organizing vectors

        Returns:
            True if successful

        Raises:
            VillageMemoryError: If storage fails
        """
        if not self._index:
            raise VillageMemoryError("Vector memory not initialized. Call initialize() first.")

        try:
            self._index.upsert(
                vectors=[(id, vector, metadata or {})],
                namespace=namespace
            )
            return True
        except Exception as e:
            raise VillageMemoryError(f"Failed to store vector: {str(e)}") from e

    async def store_batch(
        self,
        vectors: List[Tuple[str, List[float], Dict[str, Any]]],
        namespace: str = ""
    ) -> bool:
        """Store multiple vectors in batch.

        Args:
            vectors: List of (id, vector, metadata) tuples
            namespace: Optional namespace

        Returns:
            True if successful

        Raises:
            VillageMemoryError: If batch storage fails
        """
        if not self._index:
            raise VillageMemoryError("Vector memory not initialized. Call initialize() first.")

        try:
            self._index.upsert(vectors=vectors, namespace=namespace)
            return True
        except Exception as e:
            raise VillageMemoryError(f"Failed to store batch: {str(e)}") from e

    async def search(
        self,
        vector: List[float],
        top_k: int = 5,
        namespace: str = "",
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors.

        Args:
            vector: Query vector
            top_k: Number of results to return
            namespace: Optional namespace to search in
            filter: Optional metadata filter
            include_metadata: Whether to include metadata in results

        Returns:
            List of matching results with scores and metadata

        Raises:
            VillageMemoryError: If search fails
        """
        if not self._index:
            raise VillageMemoryError("Vector memory not initialized. Call initialize() first.")

        try:
            results = self._index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace,
                filter=filter,
                include_metadata=include_metadata
            )

            return [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata if include_metadata else {}
                }
                for match in results.matches
            ]
        except Exception as e:
            raise VillageMemoryError(f"Failed to search vectors: {str(e)}") from e

    async def delete(
        self,
        ids: List[str],
        namespace: str = ""
    ) -> bool:
        """Delete vectors by ID.

        Args:
            ids: List of vector IDs to delete
            namespace: Optional namespace

        Returns:
            True if successful

        Raises:
            VillageMemoryError: If deletion fails
        """
        if not self._index:
            raise VillageMemoryError("Vector memory not initialized. Call initialize() first.")

        try:
            self._index.delete(ids=ids, namespace=namespace)
            return True
        except Exception as e:
            raise VillageMemoryError(f"Failed to delete vectors: {str(e)}") from e

    async def delete_namespace(self, namespace: str) -> bool:
        """Delete all vectors in a namespace.

        Args:
            namespace: Namespace to clear

        Returns:
            True if successful

        Raises:
            VillageMemoryError: If deletion fails
        """
        if not self._index:
            raise VillageMemoryError("Vector memory not initialized. Call initialize() first.")

        try:
            self._index.delete(delete_all=True, namespace=namespace)
            return True
        except Exception as e:
            raise VillageMemoryError(f"Failed to delete namespace: {str(e)}") from e

    async def get_stats(self) -> Dict[str, Any]:
        """Get index statistics.

        Returns:
            Dictionary with index statistics

        Raises:
            VillageMemoryError: If stats retrieval fails
        """
        if not self._index:
            raise VillageMemoryError("Vector memory not initialized. Call initialize() first.")

        try:
            stats = self._index.describe_index_stats()
            return {
                "dimension": stats.dimension,
                "index_fullness": stats.index_fullness,
                "total_vector_count": stats.total_vector_count,
                "namespaces": stats.namespaces
            }
        except Exception as e:
            raise VillageMemoryError(f"Failed to get stats: {str(e)}") from e

    async def health_check(self) -> bool:
        """Check if vector storage is healthy.

        Returns:
            True if healthy
        """
        if not self._index:
            return False

        try:
            self._index.describe_index_stats()
            return True
        except Exception:
            return False


def vector_storage_available() -> bool:
    """Check if vector storage is available.

    Returns:
        True if Pinecone package is installed
    """
    return PINECONE_AVAILABLE
