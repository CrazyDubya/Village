"""AWS Bedrock LLM Provider Implementation.

This module provides integration with AWS Bedrock for accessing Claude,
Titan, Llama, and other models via AWS infrastructure.
"""

import os
import json
from typing import Any, Dict, List, Optional

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

from village.llm.base import BaseLLMProvider
from village.exceptions import LLMProviderError


class BedrockProvider(BaseLLMProvider):
    """AWS Bedrock LLM Provider for Claude, Titan, Llama, and other models.

    Attributes:
        model_id: Bedrock model ID (e.g., 'anthropic.claude-v2', 'amazon.titan-text-express-v1')
        region: AWS region
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
        aws_session_token: Optional AWS session token
    """

    # Model ID constants
    CLAUDE_V2 = "anthropic.claude-v2"
    CLAUDE_V2_1 = "anthropic.claude-v2:1"
    CLAUDE_V3_SONNET = "anthropic.claude-3-sonnet-20240229-v1:0"
    CLAUDE_V3_HAIKU = "anthropic.claude-3-haiku-20240307-v1:0"
    CLAUDE_V3_OPUS = "anthropic.claude-3-opus-20240229-v1:0"
    CLAUDE_INSTANT = "anthropic.claude-instant-v1"

    TITAN_TEXT_EXPRESS = "amazon.titan-text-express-v1"
    TITAN_TEXT_LITE = "amazon.titan-text-lite-v1"
    TITAN_EMBED_TEXT = "amazon.titan-embed-text-v1"

    LLAMA2_13B = "meta.llama2-13b-chat-v1"
    LLAMA2_70B = "meta.llama2-70b-chat-v1"

    def __init__(
        self,
        model_id: str = CLAUDE_V3_HAIKU,
        region: str = "us-east-1",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """Initialize AWS Bedrock provider.

        Args:
            model_id: Bedrock model ID
            region: AWS region (defaults to us-east-1)
            aws_access_key_id: AWS access key (defaults to env var or IAM role)
            aws_secret_access_key: AWS secret key (defaults to env var or IAM role)
            aws_session_token: Optional session token
            **kwargs: Additional configuration options

        Raises:
            LLMProviderError: If boto3 is not installed
        """
        if not BOTO3_AVAILABLE:
            raise LLMProviderError(
                "boto3 package not installed. Install with: pip install boto3>=1.28.0"
            )

        self.model_id = model_id
        self.region = region
        self.config = kwargs

        # Initialize boto3 client
        session_kwargs = {
            "region_name": region,
        }

        if aws_access_key_id:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            session_kwargs["aws_session_token"] = aws_session_token

        self.session = boto3.Session(**session_kwargs)
        self._client = self.session.client("bedrock-runtime")

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
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            **kwargs: Additional generation parameters

        Returns:
            Generated text completion

        Raises:
            LLMProviderError: If generation fails
        """
        try:
            # Build request body based on model type
            if "anthropic.claude" in self.model_id:
                body = self._build_claude_request(prompt, max_tokens, temperature, **kwargs)
            elif "amazon.titan" in self.model_id:
                body = self._build_titan_request(prompt, max_tokens, temperature, **kwargs)
            elif "meta.llama" in self.model_id:
                body = self._build_llama_request(prompt, max_tokens, temperature, **kwargs)
            else:
                raise LLMProviderError(f"Unsupported model type: {self.model_id}")

            # Invoke model
            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )

            # Parse response
            response_body = json.loads(response["body"].read())

            return self._extract_text(response_body)

        except ClientError as e:
            raise LLMProviderError(f"AWS Bedrock error: {str(e)}") from e
        except Exception as e:
            raise LLMProviderError(f"Bedrock generation failed: {str(e)}") from e

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
            # Convert messages to prompt format for models that don't support chat directly
            if "anthropic.claude-3" in self.model_id:
                # Claude 3 supports messages format
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "messages": messages,
                    "max_tokens": max_tokens or 2048,
                    "temperature": temperature,
                }
                body.update(kwargs)
            else:
                # Convert to prompt format
                prompt = self._messages_to_prompt(messages)
                return await self.generate(prompt, max_tokens, temperature, **kwargs)

            response = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )

            response_body = json.loads(response["body"].read())
            return self._extract_text(response_body)

        except ClientError as e:
            raise LLMProviderError(f"AWS Bedrock error: {str(e)}") from e
        except Exception as e:
            raise LLMProviderError(f"Bedrock chat completion failed: {str(e)}") from e

    def _build_claude_request(
        self,
        prompt: str,
        max_tokens: Optional[int],
        temperature: float,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build request body for Claude models."""
        body = {
            "prompt": f"\n\nHuman: {prompt}\n\nAssistant:",
            "max_tokens_to_sample": max_tokens or 2048,
            "temperature": temperature,
            "top_p": kwargs.get("top_p", 0.9),
            "stop_sequences": kwargs.get("stop_sequences", ["\n\nHuman:"]),
        }
        return body

    def _build_titan_request(
        self,
        prompt: str,
        max_tokens: Optional[int],
        temperature: float,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build request body for Titan models."""
        body = {
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": max_tokens or 2048,
                "temperature": temperature,
                "topP": kwargs.get("top_p", 0.9),
                "stopSequences": kwargs.get("stop_sequences", []),
            }
        }
        return body

    def _build_llama_request(
        self,
        prompt: str,
        max_tokens: Optional[int],
        temperature: float,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build request body for Llama models."""
        body = {
            "prompt": prompt,
            "max_gen_len": max_tokens or 2048,
            "temperature": temperature,
            "top_p": kwargs.get("top_p", 0.9),
        }
        return body

    def _extract_text(self, response_body: Dict[str, Any]) -> str:
        """Extract text from response based on model type."""
        if "anthropic.claude" in self.model_id:
            if "content" in response_body:
                # Claude 3 format
                return response_body["content"][0]["text"]
            else:
                # Claude 2 format
                return response_body.get("completion", "")
        elif "amazon.titan" in self.model_id:
            results = response_body.get("results", [{}])
            return results[0].get("outputText", "")
        elif "meta.llama" in self.model_id:
            return response_body.get("generation", "")
        else:
            return str(response_body)

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert chat messages to a single prompt."""
        prompt_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                prompt_parts.append(f"Human: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
            elif role == "system":
                prompt_parts.append(f"System: {content}")

        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)

    def validate_config(self) -> bool:
        """Validate provider configuration.

        Returns:
            True if configuration is valid

        Raises:
            LLMProviderError: If configuration is invalid
        """
        if not self.model_id:
            raise LLMProviderError("Model ID is required")

        # Test AWS credentials by listing models
        try:
            self._client.list_foundation_models(maxResults=1)
            return True
        except ClientError as e:
            raise LLMProviderError(
                f"Failed to validate AWS credentials: {str(e)}"
            ) from e
        except Exception as e:
            raise LLMProviderError(
                f"Failed to validate Bedrock configuration: {str(e)}"
            ) from e

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model.

        Returns:
            Dictionary containing model information
        """
        try:
            response = self._client.get_foundation_model(
                modelIdentifier=self.model_id
            )

            model_details = response.get("modelDetails", {})

            return {
                "id": self.model_id,
                "provider": "aws_bedrock",
                "model": self.model_id,
                "region": self.region,
                "model_name": model_details.get("modelName"),
                "provider_name": model_details.get("providerName"),
                "input_modalities": model_details.get("inputModalities", []),
                "output_modalities": model_details.get("outputModalities", []),
                "response_streaming_supported": model_details.get("responseStreamingSupported"),
            }
        except Exception as e:
            return {
                "id": self.model_id,
                "provider": "aws_bedrock",
                "model": self.model_id,
                "region": self.region,
                "error": str(e)
            }

    def list_available_models(self) -> List[Dict[str, Any]]:
        """List all available Bedrock models.

        Returns:
            List of model information dictionaries

        Raises:
            LLMProviderError: If listing fails
        """
        try:
            response = self._client.list_foundation_models()
            models = []

            for model in response.get("modelSummaries", []):
                models.append({
                    "model_id": model.get("modelId"),
                    "model_name": model.get("modelName"),
                    "provider_name": model.get("providerName"),
                    "input_modalities": model.get("inputModalities", []),
                    "output_modalities": model.get("outputModalities", []),
                })

            return models
        except ClientError as e:
            raise LLMProviderError(f"Failed to list models: {str(e)}") from e

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
            # Build request body
            if "anthropic.claude" in self.model_id:
                body = self._build_claude_request(prompt, max_tokens, temperature, **kwargs)
            elif "amazon.titan" in self.model_id:
                body = self._build_titan_request(prompt, max_tokens, temperature, **kwargs)
            elif "meta.llama" in self.model_id:
                body = self._build_llama_request(prompt, max_tokens, temperature, **kwargs)
            else:
                raise LLMProviderError(f"Unsupported model type: {self.model_id}")

            # Invoke model with streaming
            response = self._client.invoke_model_with_response_stream(
                modelId=self.model_id,
                body=json.dumps(body)
            )

            # Process stream
            for event in response.get("body"):
                chunk = json.loads(event["chunk"]["bytes"])

                if "anthropic.claude" in self.model_id:
                    if "completion" in chunk:
                        yield chunk["completion"]
                    elif "delta" in chunk:
                        yield chunk["delta"].get("text", "")
                elif "amazon.titan" in self.model_id:
                    yield chunk.get("outputText", "")
                elif "meta.llama" in self.model_id:
                    yield chunk.get("generation", "")

        except ClientError as e:
            raise LLMProviderError(f"AWS Bedrock streaming error: {str(e)}") from e
        except Exception as e:
            raise LLMProviderError(f"Bedrock streaming failed: {str(e)}") from e
