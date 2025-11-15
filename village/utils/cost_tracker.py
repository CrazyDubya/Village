"""Cost tracking and analytics for LLM usage."""

import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json


@dataclass
class UsageRecord:
    """Record of LLM API usage.

    Attributes:
        timestamp: When the request was made
        provider: LLM provider name
        model: Model name
        villager_id: ID of villager making the request
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        total_tokens: Total tokens used
        cost: Estimated cost in USD
        duration: Request duration in seconds
        success: Whether the request succeeded
        metadata: Additional metadata
    """
    timestamp: datetime
    provider: str
    model: str
    villager_id: Optional[str] = None
    village_id: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    duration: float = 0.0
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostTracker:
    """Track and analyze LLM usage costs.

    Provides detailed cost tracking, analytics, and budget management
    for LLM API usage across providers, models, and villagers.
    """

    # Pricing per 1K tokens (as of 2025-11)
    PRICING = {
        "openai": {
            "gpt-4": {"prompt": 0.03, "completion": 0.06},
            "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
            "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
            "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
            "gpt-3.5-turbo-16k": {"prompt": 0.003, "completion": 0.004},
        },
        "anthropic": {
            "claude-3-opus": {"prompt": 0.015, "completion": 0.075},
            "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
            "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
            "claude-2": {"prompt": 0.008, "completion": 0.024},
            "claude-instant": {"prompt": 0.0008, "completion": 0.0024},
        },
        "google": {
            "gemini-pro": {"prompt": 0.00025, "completion": 0.0005},
            "gemini-pro-vision": {"prompt": 0.00025, "completion": 0.0005},
            "gemini-1.5-pro": {"prompt": 0.0035, "completion": 0.0105},
            "gemini-1.5-flash": {"prompt": 0.000175, "completion": 0.000525},
        },
        "aws_bedrock": {
            "anthropic.claude-3-opus": {"prompt": 0.015, "completion": 0.075},
            "anthropic.claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
            "anthropic.claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
            "anthropic.claude-v2": {"prompt": 0.008, "completion": 0.024},
            "amazon.titan-text-express": {"prompt": 0.0008, "completion": 0.0016},
            "amazon.titan-text-lite": {"prompt": 0.0003, "completion": 0.0004},
            "meta.llama2-13b-chat": {"prompt": 0.00075, "completion": 0.001},
            "meta.llama2-70b-chat": {"prompt": 0.00195, "completion": 0.00256},
        },
        "ollama": {
            "default": {"prompt": 0.0, "completion": 0.0},  # Local = free
        }
    }

    def __init__(self) -> None:
        """Initialize cost tracker."""
        self.records: List[UsageRecord] = []
        self.budgets: Dict[str, float] = {}  # entity_id -> budget limit
        self.alerts: List[Dict[str, Any]] = []

    def record_usage(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        villager_id: Optional[str] = None,
        village_id: Optional[str] = None,
        duration: float = 0.0,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UsageRecord:
        """Record LLM usage.

        Args:
            provider: Provider name (openai, anthropic, google, aws_bedrock, ollama)
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            villager_id: Optional villager ID
            village_id: Optional village ID
            duration: Request duration in seconds
            success: Whether request succeeded
            metadata: Additional metadata

        Returns:
            Created usage record
        """
        total_tokens = prompt_tokens + completion_tokens
        cost = self.calculate_cost(provider, model, prompt_tokens, completion_tokens)

        record = UsageRecord(
            timestamp=datetime.now(),
            provider=provider,
            model=model,
            villager_id=villager_id,
            village_id=village_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            duration=duration,
            success=success,
            metadata=metadata or {}
        )

        self.records.append(record)

        # Check budgets
        self._check_budgets(record)

        return record

    def calculate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> float:
        """Calculate cost for token usage.

        Args:
            provider: Provider name
            model: Model name
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens

        Returns:
            Estimated cost in USD
        """
        provider_lower = provider.lower()
        model_lower = model.lower()

        # Find matching pricing
        pricing = None

        if provider_lower in self.PRICING:
            provider_pricing = self.PRICING[provider_lower]

            # Try exact match first
            if model_lower in provider_pricing:
                pricing = provider_pricing[model_lower]
            else:
                # Try prefix match
                for model_key, model_pricing in provider_pricing.items():
                    if model_lower.startswith(model_key):
                        pricing = model_pricing
                        break

        # Ollama is always free
        if provider_lower == "ollama":
            return 0.0

        # Default pricing if not found
        if pricing is None:
            pricing = {"prompt": 0.001, "completion": 0.002}

        prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
        completion_cost = (completion_tokens / 1000) * pricing["completion"]

        return prompt_cost + completion_cost

    def get_usage_summary(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        villager_id: Optional[str] = None,
        village_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get usage summary for a time period.

        Args:
            start_time: Start of time range (default: all time)
            end_time: End of time range (default: now)
            villager_id: Filter by villager
            village_id: Filter by village
            provider: Filter by provider

        Returns:
            Summary statistics
        """
        filtered_records = self._filter_records(
            start_time, end_time, villager_id, village_id, provider
        )

        if not filtered_records:
            return {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_cost": 0.0,
                "average_cost_per_request": 0.0,
                "average_tokens_per_request": 0.0,
                "total_duration": 0.0,
                "average_duration": 0.0,
            }

        total_requests = len(filtered_records)
        successful = sum(1 for r in filtered_records if r.success)
        failed = total_requests - successful
        total_tokens = sum(r.total_tokens for r in filtered_records)
        prompt_tokens = sum(r.prompt_tokens for r in filtered_records)
        completion_tokens = sum(r.completion_tokens for r in filtered_records)
        total_cost = sum(r.cost for r in filtered_records)
        total_duration = sum(r.duration for r in filtered_records)

        return {
            "total_requests": total_requests,
            "successful_requests": successful,
            "failed_requests": failed,
            "success_rate": successful / total_requests if total_requests > 0 else 0.0,
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_cost": round(total_cost, 4),
            "average_cost_per_request": round(total_cost / total_requests, 4) if total_requests > 0 else 0.0,
            "average_tokens_per_request": total_tokens // total_requests if total_requests > 0 else 0,
            "total_duration": round(total_duration, 2),
            "average_duration": round(total_duration / total_requests, 3) if total_requests > 0 else 0.0,
        }

    def get_cost_by_provider(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get cost breakdown by provider.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Dictionary mapping provider to cost
        """
        filtered_records = self._filter_records(start_time, end_time)

        costs = defaultdict(float)
        for record in filtered_records:
            costs[record.provider] += record.cost

        return dict(costs)

    def get_cost_by_model(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        provider: Optional[str] = None
    ) -> Dict[str, float]:
        """Get cost breakdown by model.

        Args:
            start_time: Start of time range
            end_time: End of time range
            provider: Filter by provider

        Returns:
            Dictionary mapping model to cost
        """
        filtered_records = self._filter_records(start_time, end_time, provider=provider)

        costs = defaultdict(float)
        for record in filtered_records:
            model_key = f"{record.provider}:{record.model}"
            costs[model_key] += record.cost

        return dict(costs)

    def get_cost_by_villager(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Get cost breakdown by villager.

        Args:
            start_time: Start of time range
            end_time: End of time range

        Returns:
            Dictionary mapping villager ID to cost
        """
        filtered_records = self._filter_records(start_time, end_time)

        costs = defaultdict(float)
        for record in filtered_records:
            if record.villager_id:
                costs[record.villager_id] += record.cost

        return dict(costs)

    def set_budget(
        self,
        entity_id: str,
        limit: float,
        period: str = "daily"
    ) -> None:
        """Set budget limit for an entity (villager, village, etc).

        Args:
            entity_id: Entity identifier
            limit: Budget limit in USD
            period: Budget period (hourly, daily, weekly, monthly)
        """
        key = f"{entity_id}:{period}"
        self.budgets[key] = limit

    def get_budget_status(
        self,
        entity_id: str,
        period: str = "daily"
    ) -> Dict[str, Any]:
        """Get budget status for an entity.

        Args:
            entity_id: Entity identifier
            period: Budget period

        Returns:
            Budget status information
        """
        key = f"{entity_id}:{period}"
        limit = self.budgets.get(key, 0.0)

        if limit == 0.0:
            return {"limit": 0.0, "used": 0.0, "remaining": 0.0, "percentage": 0.0}

        # Calculate time range based on period
        now = datetime.now()
        if period == "hourly":
            start_time = now - timedelta(hours=1)
        elif period == "daily":
            start_time = now - timedelta(days=1)
        elif period == "weekly":
            start_time = now - timedelta(weeks=1)
        elif period == "monthly":
            start_time = now - timedelta(days=30)
        else:
            start_time = None

        # Get usage for entity
        if entity_id.startswith("villager:"):
            villager_id = entity_id.split(":", 1)[1]
            summary = self.get_usage_summary(
                start_time=start_time,
                villager_id=villager_id
            )
        elif entity_id.startswith("village:"):
            village_id = entity_id.split(":", 1)[1]
            summary = self.get_usage_summary(
                start_time=start_time,
                village_id=village_id
            )
        else:
            summary = self.get_usage_summary(start_time=start_time)

        used = summary["total_cost"]
        remaining = max(0.0, limit - used)
        percentage = (used / limit * 100) if limit > 0 else 0.0

        return {
            "limit": limit,
            "used": round(used, 4),
            "remaining": round(remaining, 4),
            "percentage": round(percentage, 2),
            "exceeded": used > limit
        }

    def _filter_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        villager_id: Optional[str] = None,
        village_id: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[UsageRecord]:
        """Filter records by criteria."""
        filtered = self.records

        if start_time:
            filtered = [r for r in filtered if r.timestamp >= start_time]

        if end_time:
            filtered = [r for r in filtered if r.timestamp <= end_time]

        if villager_id:
            filtered = [r for r in filtered if r.villager_id == villager_id]

        if village_id:
            filtered = [r for r in filtered if r.village_id == village_id]

        if provider:
            filtered = [r for r in filtered if r.provider.lower() == provider.lower()]

        return filtered

    def _check_budgets(self, record: UsageRecord) -> None:
        """Check if any budgets are exceeded and generate alerts."""
        entities_to_check = []

        if record.villager_id:
            entities_to_check.append(f"villager:{record.villager_id}")

        if record.village_id:
            entities_to_check.append(f"village:{record.village_id}")

        for entity_id in entities_to_check:
            for period in ["hourly", "daily", "weekly", "monthly"]:
                status = self.get_budget_status(entity_id, period)

                if status["exceeded"]:
                    alert = {
                        "timestamp": datetime.now(),
                        "entity_id": entity_id,
                        "period": period,
                        "limit": status["limit"],
                        "used": status["used"],
                        "percentage": status["percentage"],
                    }
                    self.alerts.append(alert)

    def export_records(
        self,
        filepath: str,
        format: str = "json"
    ) -> None:
        """Export usage records to file.

        Args:
            filepath: Path to output file
            format: Export format (json or csv)
        """
        if format == "json":
            data = [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "provider": r.provider,
                    "model": r.model,
                    "villager_id": r.villager_id,
                    "village_id": r.village_id,
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "total_tokens": r.total_tokens,
                    "cost": r.cost,
                    "duration": r.duration,
                    "success": r.success,
                }
                for r in self.records
            ]

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

        elif format == "csv":
            import csv

            with open(filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "provider", "model", "villager_id", "village_id",
                    "prompt_tokens", "completion_tokens", "total_tokens",
                    "cost", "duration", "success"
                ])

                for r in self.records:
                    writer.writerow([
                        r.timestamp.isoformat(),
                        r.provider,
                        r.model,
                        r.villager_id or "",
                        r.village_id or "",
                        r.prompt_tokens,
                        r.completion_tokens,
                        r.total_tokens,
                        f"{r.cost:.6f}",
                        f"{r.duration:.3f}",
                        r.success,
                    ])


# Global cost tracker instance
_cost_tracker_instance: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get global cost tracker instance.

    Returns:
        CostTracker instance
    """
    global _cost_tracker_instance

    if _cost_tracker_instance is None:
        _cost_tracker_instance = CostTracker()

    return _cost_tracker_instance
