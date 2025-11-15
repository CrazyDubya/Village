"""Enhanced quota management for resource control."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import asyncio


class QuotaPeriod(Enum):
    """Quota period types."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class QuotaAction(Enum):
    """Actions to take when quota exceeded."""
    BLOCK = "block"  # Block requests
    THROTTLE = "throttle"  # Slow down requests
    WARN = "warn"  # Log warning but allow
    ALERT = "alert"  # Send alert but allow


@dataclass
class QuotaLimit:
    """Quota limit configuration.

    Attributes:
        limit: Maximum value
        period: Time period for the limit
        action: Action when exceeded
        soft_limit: Optional warning threshold (0-1 of limit)
    """
    limit: float
    period: QuotaPeriod
    action: QuotaAction
    soft_limit: Optional[float] = None


@dataclass
class QuotaUsage:
    """Current quota usage.

    Attributes:
        used: Amount used
        limit: Maximum allowed
        period: Time period
        percentage: Usage percentage
        exceeded: Whether limit is exceeded
        soft_exceeded: Whether soft limit is exceeded
    """
    used: float
    limit: float
    period: QuotaPeriod
    percentage: float
    exceeded: bool
    soft_exceeded: bool


class QuotaManager:
    """Manage quotas for different entities and resources.

    Provides fine-grained control over resource usage with:
    - Multiple quota types (requests, tokens, cost)
    - Per-entity quotas (villager, village, global)
    - Multiple periods (hourly, daily, weekly, monthly)
    - Configurable actions (block, throttle, warn, alert)
    """

    def __init__(self) -> None:
        """Initialize quota manager."""
        self.quotas: Dict[str, Dict[str, QuotaLimit]] = {}  # entity_id -> quota_type -> limit
        self.usage: Dict[str, List[Dict[str, Any]]] = {}  # entity_id -> usage records
        self.alerts: List[Dict[str, Any]] = []
        self.callbacks: Dict[str, List[callable]] = {}  # event_type -> callbacks

    def set_quota(
        self,
        entity_id: str,
        quota_type: str,
        limit: float,
        period: QuotaPeriod,
        action: QuotaAction = QuotaAction.BLOCK,
        soft_limit: Optional[float] = 0.8
    ) -> None:
        """Set quota limit for an entity.

        Args:
            entity_id: Entity identifier (e.g., "villager:xyz", "village:abc", "global")
            quota_type: Type of quota (requests, tokens, cost)
            limit: Maximum value
            period: Time period
            action: Action when exceeded
            soft_limit: Soft limit threshold (0-1), triggers warning
        """
        if entity_id not in self.quotas:
            self.quotas[entity_id] = {}

        self.quotas[entity_id][quota_type] = QuotaLimit(
            limit=limit,
            period=period,
            action=action,
            soft_limit=soft_limit
        )

    def record_usage(
        self,
        entity_id: str,
        quota_type: str,
        amount: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> QuotaUsage:
        """Record resource usage.

        Args:
            entity_id: Entity identifier
            quota_type: Type of quota
            amount: Amount used
            metadata: Additional metadata

        Returns:
            Current quota usage status

        Raises:
            QuotaExceededError: If quota is exceeded and action is BLOCK
        """
        # Initialize usage tracking if needed
        if entity_id not in self.usage:
            self.usage[entity_id] = []

        # Record usage
        record = {
            "timestamp": datetime.now(),
            "quota_type": quota_type,
            "amount": amount,
            "metadata": metadata or {}
        }
        self.usage[entity_id].append(record)

        # Check quota
        usage_status = self.check_quota(entity_id, quota_type)

        # Handle quota exceeded
        if usage_status.exceeded:
            quota_limit = self.quotas.get(entity_id, {}).get(quota_type)

            if quota_limit:
                if quota_limit.action == QuotaAction.BLOCK:
                    raise QuotaExceededError(
                        f"Quota exceeded for {entity_id} ({quota_type}): "
                        f"{usage_status.used}/{usage_status.limit}"
                    )
                elif quota_limit.action == QuotaAction.ALERT:
                    self._trigger_alert(entity_id, quota_type, usage_status)
                elif quota_limit.action == QuotaAction.WARN:
                    self._trigger_warning(entity_id, quota_type, usage_status)

        elif usage_status.soft_exceeded:
            self._trigger_warning(entity_id, quota_type, usage_status)

        return usage_status

    def check_quota(
        self,
        entity_id: str,
        quota_type: str
    ) -> QuotaUsage:
        """Check current quota usage.

        Args:
            entity_id: Entity identifier
            quota_type: Type of quota

        Returns:
            Current usage status
        """
        quota_limit = self.quotas.get(entity_id, {}).get(quota_type)

        if not quota_limit:
            return QuotaUsage(
                used=0,
                limit=float('inf'),
                period=QuotaPeriod.DAILY,
                percentage=0,
                exceeded=False,
                soft_exceeded=False
            )

        # Get usage in the relevant time period
        now = datetime.now()
        period_start = self._get_period_start(now, quota_limit.period)

        usage_records = self.usage.get(entity_id, [])
        used = sum(
            r["amount"]
            for r in usage_records
            if r["quota_type"] == quota_type and r["timestamp"] >= period_start
        )

        percentage = (used / quota_limit.limit * 100) if quota_limit.limit > 0 else 0
        exceeded = used > quota_limit.limit

        soft_exceeded = False
        if quota_limit.soft_limit:
            soft_threshold = quota_limit.limit * quota_limit.soft_limit
            soft_exceeded = used > soft_threshold and not exceeded

        return QuotaUsage(
            used=used,
            limit=quota_limit.limit,
            period=quota_limit.period,
            percentage=round(percentage, 2),
            exceeded=exceeded,
            soft_exceeded=soft_exceeded
        )

    def get_all_quotas(self, entity_id: str) -> Dict[str, QuotaUsage]:
        """Get usage status for all quotas of an entity.

        Args:
            entity_id: Entity identifier

        Returns:
            Dictionary mapping quota type to usage status
        """
        result = {}

        entity_quotas = self.quotas.get(entity_id, {})
        for quota_type in entity_quotas.keys():
            result[quota_type] = self.check_quota(entity_id, quota_type)

        return result

    def reset_quota(
        self,
        entity_id: str,
        quota_type: Optional[str] = None
    ) -> None:
        """Reset quota usage for an entity.

        Args:
            entity_id: Entity identifier
            quota_type: Specific quota type to reset (None = all)
        """
        if entity_id not in self.usage:
            return

        if quota_type:
            # Remove specific quota type records
            self.usage[entity_id] = [
                r for r in self.usage[entity_id]
                if r["quota_type"] != quota_type
            ]
        else:
            # Remove all records
            self.usage[entity_id] = []

    def register_callback(
        self,
        event_type: str,
        callback: callable
    ) -> None:
        """Register callback for quota events.

        Args:
            event_type: Event type (exceeded, soft_exceeded, reset)
            callback: Callback function
        """
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []

        self.callbacks[event_type].append(callback)

    def _trigger_alert(
        self,
        entity_id: str,
        quota_type: str,
        usage: QuotaUsage
    ) -> None:
        """Trigger alert for quota exceeded."""
        alert = {
            "timestamp": datetime.now(),
            "entity_id": entity_id,
            "quota_type": quota_type,
            "used": usage.used,
            "limit": usage.limit,
            "percentage": usage.percentage,
            "severity": "error"
        }

        self.alerts.append(alert)

        # Call registered callbacks
        for callback in self.callbacks.get("exceeded", []):
            try:
                callback(alert)
            except Exception:
                pass  # Don't let callback errors break quota management

    def _trigger_warning(
        self,
        entity_id: str,
        quota_type: str,
        usage: QuotaUsage
    ) -> None:
        """Trigger warning for soft limit exceeded."""
        warning = {
            "timestamp": datetime.now(),
            "entity_id": entity_id,
            "quota_type": quota_type,
            "used": usage.used,
            "limit": usage.limit,
            "percentage": usage.percentage,
            "severity": "warning"
        }

        self.alerts.append(warning)

        # Call registered callbacks
        for callback in self.callbacks.get("soft_exceeded", []):
            try:
                callback(warning)
            except Exception:
                pass

    def _get_period_start(
        self,
        current_time: datetime,
        period: QuotaPeriod
    ) -> datetime:
        """Get start time for a quota period."""
        if period == QuotaPeriod.HOURLY:
            return current_time - timedelta(hours=1)
        elif period == QuotaPeriod.DAILY:
            return current_time - timedelta(days=1)
        elif period == QuotaPeriod.WEEKLY:
            return current_time - timedelta(weeks=1)
        elif period == QuotaPeriod.MONTHLY:
            return current_time - timedelta(days=30)
        elif period == QuotaPeriod.YEARLY:
            return current_time - timedelta(days=365)
        else:
            return current_time - timedelta(days=1)

    def get_alerts(
        self,
        severity: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get quota alerts.

        Args:
            severity: Filter by severity (error, warning)
            since: Filter by time

        Returns:
            List of alerts
        """
        filtered = self.alerts

        if severity:
            filtered = [a for a in filtered if a["severity"] == severity]

        if since:
            filtered = [a for a in filtered if a["timestamp"] >= since]

        return filtered

    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self.alerts = []


class QuotaExceededError(Exception):
    """Exception raised when quota is exceeded."""
    pass


# Global quota manager instance
_quota_manager_instance: Optional[QuotaManager] = None


def get_quota_manager() -> QuotaManager:
    """Get global quota manager instance.

    Returns:
        QuotaManager instance
    """
    global _quota_manager_instance

    if _quota_manager_instance is None:
        _quota_manager_instance = QuotaManager()

    return _quota_manager_instance
