"""Unit tests for cost tracking."""

import pytest
from datetime import datetime, timedelta
from village.utils.cost_tracker import CostTracker, UsageRecord


def test_cost_tracker_initialization():
    """Test cost tracker initialization."""
    tracker = CostTracker()
    assert len(tracker.records) == 0
    assert len(tracker.budgets) == 0


def test_calculate_cost_openai():
    """Test cost calculation for OpenAI."""
    tracker = CostTracker()

    # GPT-4
    cost = tracker.calculate_cost("openai", "gpt-4", 1000, 500)
    assert cost > 0
    assert cost == (1000 / 1000 * 0.03) + (500 / 1000 * 0.06)

    # GPT-3.5 Turbo
    cost = tracker.calculate_cost("openai", "gpt-3.5-turbo", 1000, 500)
    assert cost == (1000 / 1000 * 0.0005) + (500 / 1000 * 0.0015)


def test_calculate_cost_anthropic():
    """Test cost calculation for Anthropic."""
    tracker = CostTracker()

    # Claude 3 Opus
    cost = tracker.calculate_cost("anthropic", "claude-3-opus", 1000, 500)
    assert cost == (1000 / 1000 * 0.015) + (500 / 1000 * 0.075)


def test_calculate_cost_ollama_free():
    """Test that Ollama is free."""
    tracker = CostTracker()

    cost = tracker.calculate_cost("ollama", "llama2", 1000, 500)
    assert cost == 0.0


def test_record_usage():
    """Test recording usage."""
    tracker = CostTracker()

    record = tracker.record_usage(
        provider="openai",
        model="gpt-4",
        prompt_tokens=100,
        completion_tokens=50,
        villager_id="test_villager"
    )

    assert isinstance(record, UsageRecord)
    assert record.provider == "openai"
    assert record.model == "gpt-4"
    assert record.prompt_tokens == 100
    assert record.completion_tokens == 50
    assert record.total_tokens == 150
    assert record.cost > 0
    assert len(tracker.records) == 1


def test_usage_summary():
    """Test usage summary."""
    tracker = CostTracker()

    # Record some usage
    tracker.record_usage("openai", "gpt-4", 100, 50)
    tracker.record_usage("openai", "gpt-4", 200, 100)
    tracker.record_usage("anthropic", "claude-3-haiku", 150, 75)

    summary = tracker.get_usage_summary()

    assert summary["total_requests"] == 3
    assert summary["total_tokens"] == 675
    assert summary["prompt_tokens"] == 450
    assert summary["completion_tokens"] == 225
    assert summary["total_cost"] > 0


def test_cost_by_provider():
    """Test cost breakdown by provider."""
    tracker = CostTracker()

    tracker.record_usage("openai", "gpt-4", 100, 50)
    tracker.record_usage("anthropic", "claude-3-haiku", 100, 50)

    costs = tracker.get_cost_by_provider()

    assert "openai" in costs
    assert "anthropic" in costs
    assert costs["openai"] > 0
    assert costs["anthropic"] > 0


def test_cost_by_villager():
    """Test cost breakdown by villager."""
    tracker = CostTracker()

    tracker.record_usage("openai", "gpt-4", 100, 50, villager_id="villager1")
    tracker.record_usage("openai", "gpt-4", 100, 50, villager_id="villager2")
    tracker.record_usage("openai", "gpt-4", 100, 50, villager_id="villager1")

    costs = tracker.get_cost_by_villager()

    assert "villager1" in costs
    assert "villager2" in costs
    # villager1 should have ~2x the cost of villager2
    assert costs["villager1"] > costs["villager2"]


def test_budget_management():
    """Test budget setting and checking."""
    tracker = CostTracker()

    # Set budget
    tracker.set_budget("villager:test", limit=1.0, period="daily")

    # Check budget status
    status = tracker.get_budget_status("villager:test", period="daily")

    assert status["limit"] == 1.0
    assert status["used"] == 0.0
    assert status["remaining"] == 1.0
    assert status["percentage"] == 0.0
    assert status["exceeded"] == False


def test_budget_exceeded():
    """Test budget exceeded detection."""
    tracker = CostTracker()

    # Set low budget
    tracker.set_budget("villager:test", limit=0.01, period="daily")

    # Record usage that exceeds budget
    tracker.record_usage(
        "openai", "gpt-4", 1000, 500,
        villager_id="test"
    )

    # Check budget
    status = tracker.get_budget_status("villager:test", period="daily")

    assert status["exceeded"] == True


def test_time_filtering():
    """Test filtering records by time."""
    tracker = CostTracker()

    now = datetime.now()

    # Record some old usage (simulate)
    old_record = tracker.record_usage("openai", "gpt-4", 100, 50)
    old_record.timestamp = now - timedelta(days=2)

    # Record recent usage
    tracker.record_usage("openai", "gpt-4", 100, 50)

    # Get summary for last day
    summary = tracker.get_usage_summary(
        start_time=now - timedelta(days=1)
    )

    # Should only include recent usage
    assert summary["total_requests"] == 1
