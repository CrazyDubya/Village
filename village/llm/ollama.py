"""Ollama LLM Provider Implementation for local models.

This module provides integration with Ollama for running LLMs locally.
"""

import os
from typing import Any, Dict, List, Optional

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from village.llm.base import BaseLLMProvider
from village.exceptions import LLMProviderError


class OllamaProvider(BaseLLMProvider):
    """Ollama LLM Provider for local model execution.

    Attributes:
        model: Model name (e.g., 'llama2', 'mistral', 'codellama')
        host: Ollama server host
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        model: str = "llama2",
        host: Optional[str] = None,
        timeout: int = 120,
        **kwargs: Any
    ) -> None:
        """Initialize Ollama provider.

        Args:
            model: Model name to use (e.g., llama2, mistral, codellama, phi)
            host: Ollama server host (defaults to http://localhost:11434)
            timeout: Request timeout in seconds
            **kwargs: Additional configuration options

        Raises:
            LLMProviderError: If Ollama package is not installed
        """
        if not OLLAMA_AVAILABLE:
            raise LLMProviderError(
                "Ollama package not installed. Install with: pip install ollama>=0.1.0"
            )

        self.model = model
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.timeout = timeout
        self.config = kwargs

        # Initialize client
        self._client = ollama.Client(host=self.host)

    async def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> str:
        """Generate text completion from a prompt.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate (Ollama uses num_predict)
            temperature: Sampling temperature (0-1)
            **kwargs: Additional generation parameters

        Returns:
            Generated text completion

        Raises:
            LLMProviderError: If generation fails
        """
        try:
            options = {
                "temperature": temperature,
            }
            if max_tokens:
                options["num_predict"] = max_tokens

            # Merge with any additional options
            options.update(kwargs.get("options", {}))

            response = self._client.generate(
                model=self.model,
                prompt=prompt,
                options=options
            )

            return response["response"]

        except Exception as e:
            raise LLMProviderError(f"Ollama generation failed: {str(e)}") from e

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> str:
        """Generate chat completion from messages.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional generation parameters

        Returns:
            Generated chat response

        Raises:
            LLMProviderError: If chat completion fails
        """
        try:
            options = {
                "temperature": temperature,
            }
            if max_tokens:
                options["num_predict"] = max_tokens

            # Merge with any additional options
            options.update(kwargs.get("options", {}))

            response = self._client.chat(
                model=self.model,
                messages=messages,
                options=options
            )

            return response["message"]["content"]

        except Exception as e:
            raise LLMProviderError(f"Ollama chat completion failed: {str(e)}") from e

    def validate_config(self) -> bool:
        """Validate provider configuration.

        Returns:
            True if configuration is valid

        Raises:
            LLMProviderError: If configuration is invalid
        """
        if not self.model:
            raise LLMProviderError("Model name is required")

        # Test connection to Ollama server
        try:
            self._client.list()
            return True
        except Exception as e:
            raise LLMProviderError(
                f"Failed to connect to Ollama server at {self.host}: {str(e)}"
            ) from e

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model.

        Returns:
            Dictionary containing model information
        """
        try:
            model_info = self._client.show(self.model)
            return {
                "id": self.model,
                "provider": "ollama",
                "model": self.model,
                "host": self.host,
                "modelfile": model_info.get("modelfile", ""),
                "parameters": model_info.get("parameters", ""),
                "template": model_info.get("template", ""),
                "details": model_info.get("details", {}),
            }
        except Exception as e:
            return {
                "id": self.model,
                "provider": "ollama",
                "model": self.model,
                "host": self.host,
                "error": str(e)
            }

    def list_models(self) -> List[str]:
        """List available Ollama models.

        Returns:
            List of available model names

        Raises:
            LLMProviderError: If listing fails
        """
        try:
            models = self._client.list()
            return [model["name"] for model in models.get("models", [])]
        except Exception as e:
            raise LLMProviderError(f"Failed to list Ollama models: {str(e)}") from e

    async def pull_model(self, model: Optional[str] = None) -> bool:
        """Pull/download a model from Ollama registry.

        Args:
            model: Model name to pull (uses self.model if not specified)

        Returns:
            True if successful

        Raises:
            LLMProviderError: If pull fails
        """
        model_name = model or self.model

        try:
            self._client.pull(model_name)
            return True
        except Exception as e:
            raise LLMProviderError(f"Failed to pull model {model_name}: {str(e)}") from e

    async def delete_model(self, model: str) -> bool:
        """Delete a model from local storage.

        Args:
            model: Model name to delete

        Returns:
            True if successful

        Raises:
            LLMProviderError: If deletion fails
        """
        try:
            self._client.delete(model)
            return True
        except Exception as e:
            raise LLMProviderError(f"Failed to delete model {model}: {str(e)}") from e

    async def stream_generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs: Any
    ) -> Any:
        """Stream text generation from a prompt.

        Args:
            prompt: Input prompt text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional generation parameters

        Yields:
            Text chunks as they are generated

        Raises:
            LLMProviderError: If streaming fails
        """
        try:
            options = {
                "temperature": temperature,
            }
            if max_tokens:
                options["num_predict"] = max_tokens

            options.update(kwargs.get("options", {}))

            stream = self._client.generate(
                model=self.model,
                prompt=prompt,
                stream=True,
                options=options
            )

            for chunk in stream:
                if "response" in chunk:
                    yield chunk["response"]

        except Exception as e:
            raise LLMProviderError(f"Ollama streaming failed: {str(e)}") from e

    def get_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text.

        Args:
            text: Text to generate embeddings for

        Returns:
            Embedding vector

        Raises:
            LLMProviderError: If embedding generation fails
        """
        try:
            response = self._client.embeddings(
                model=self.model,
                prompt=text
            )
            return response["embedding"]
        except Exception as e:
            raise LLMProviderError(f"Failed to generate embeddings: {str(e)}") from e
