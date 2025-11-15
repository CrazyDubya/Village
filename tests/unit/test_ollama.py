"""Unit tests for Ollama provider."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from village.llm.ollama import OllamaProvider
from village.exceptions import LLMProviderError


@pytest.fixture
def mock_ollama_client():
    """Mock Ollama client."""
    with patch('village.llm.ollama.ollama') as mock:
        client = Mock()
        mock.Client.return_value = client
        yield client


@pytest.mark.asyncio
async def test_ollama_initialization(mock_ollama_client):
    """Test Ollama provider initialization."""
    provider = OllamaProvider(model="llama2", host="http://localhost:11434")

    assert provider.model == "llama2"
    assert provider.host == "http://localhost:11434"
    assert provider.timeout == 120


@pytest.mark.asyncio
async def test_ollama_generate(mock_ollama_client):
    """Test text generation."""
    mock_ollama_client.generate.return_value = {
        "response": "Generated text"
    }

    provider = OllamaProvider(model="llama2")
    result = await provider.generate("Test prompt")

    assert result == "Generated text"
    mock_ollama_client.generate.assert_called_once()


@pytest.mark.asyncio
async def test_ollama_chat(mock_ollama_client):
    """Test chat completion."""
    mock_ollama_client.chat.return_value = {
        "message": {"content": "Chat response"}
    }

    provider = OllamaProvider(model="llama2")
    messages = [{"role": "user", "content": "Hello"}]
    result = await provider.chat(messages)

    assert result == "Chat response"
    mock_ollama_client.chat.assert_called_once()


def test_ollama_list_models(mock_ollama_client):
    """Test listing available models."""
    mock_ollama_client.list.return_value = {
        "models": [
            {"name": "llama2"},
            {"name": "mistral"},
        ]
    }

    provider = OllamaProvider(model="llama2")
    models = provider.list_models()

    assert len(models) == 2
    assert "llama2" in models
    assert "mistral" in models


def test_ollama_get_embeddings(mock_ollama_client):
    """Test embedding generation."""
    mock_ollama_client.embeddings.return_value = {
        "embedding": [0.1, 0.2, 0.3]
    }

    provider = OllamaProvider(model="llama2")
    embeddings = provider.get_embeddings("Test text")

    assert embeddings == [0.1, 0.2, 0.3]


def test_ollama_validate_config(mock_ollama_client):
    """Test configuration validation."""
    mock_ollama_client.list.return_value = {"models": []}

    provider = OllamaProvider(model="llama2")
    assert provider.validate_config() is True


def test_ollama_get_model_info(mock_ollama_client):
    """Test getting model information."""
    mock_ollama_client.show.return_value = {
        "modelfile": "FROM llama2",
        "parameters": "temperature 0.7",
        "details": {"format": "gguf"}
    }

    provider = OllamaProvider(model="llama2")
    info = provider.get_model_info()

    assert info["provider"] == "ollama"
    assert info["model"] == "llama2"
    assert "modelfile" in info
