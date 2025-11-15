"""State management for villagers and villages."""

import json
import pickle
from typing import Any, Dict, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
import asyncio


@dataclass
class VillagerState:
    """Serializable state for a villager.

    Attributes:
        villager_id: Unique villager identifier
        name: Villager name
        role: Villager role
        conversation_history: List of messages
        memory: Villager memory dictionary
        config: Configuration dictionary
        created_at: Creation timestamp
        last_updated: Last update timestamp
        metadata: Additional metadata
    """
    villager_id: str
    name: str
    role: str
    conversation_history: list
    memory: dict
    config: dict
    created_at: datetime
    last_updated: datetime
    metadata: dict

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "villager_id": self.villager_id,
            "name": self.name,
            "role": self.role,
            "conversation_history": self.conversation_history,
            "memory": self.memory,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VillagerState":
        """Create from dictionary."""
        return cls(
            villager_id=data["villager_id"],
            name=data["name"],
            role=data["role"],
            conversation_history=data.get("conversation_history", []),
            memory=data.get("memory", {}),
            config=data.get("config", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class VillageState:
    """Serializable state for a village.

    Attributes:
        village_id: Unique village identifier
        name: Village name
        villagers: Dictionary of villager states
        task_history: List of completed tasks
        config: Configuration dictionary
        created_at: Creation timestamp
        last_updated: Last update timestamp
        metadata: Additional metadata
    """
    village_id: str
    name: str
    villagers: Dict[str, VillagerState]
    task_history: list
    config: dict
    created_at: datetime
    last_updated: datetime
    metadata: dict

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "village_id": self.village_id,
            "name": self.name,
            "villagers": {k: v.to_dict() for k, v in self.villagers.items()},
            "task_history": self.task_history,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VillageState":
        """Create from dictionary."""
        return cls(
            village_id=data["village_id"],
            name=data["name"],
            villagers={
                k: VillagerState.from_dict(v)
                for k, v in data.get("villagers", {}).items()
            },
            task_history=data.get("task_history", []),
            config=data.get("config", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            metadata=data.get("metadata", {}),
        )


class StateManager:
    """Manage state persistence for villagers and villages."""

    def __init__(self, storage_backend: Optional[Any] = None) -> None:
        """Initialize state manager.

        Args:
            storage_backend: Optional storage backend (uses in-memory if not provided)
        """
        self.storage = storage_backend
        self._cache: Dict[str, Any] = {}

    async def save_villager_state(
        self,
        villager: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Save villager state.

        Args:
            villager: Villager instance to save
            metadata: Optional additional metadata

        Returns:
            True if successful
        """
        state = VillagerState(
            villager_id=villager.id,
            name=villager.name,
            role=villager.role,
            conversation_history=getattr(villager, "conversation_history", []),
            memory=getattr(villager, "memory", {}),
            config=getattr(villager, "config", {}),
            created_at=getattr(villager, "created_at", datetime.now()),
            last_updated=datetime.now(),
            metadata=metadata or {}
        )

        if self.storage:
            await self.storage.save_villager(villager.id, state.to_dict())
        else:
            self._cache[f"villager:{villager.id}"] = state

        return True

    async def load_villager_state(
        self,
        villager_id: str
    ) -> Optional[VillagerState]:
        """Load villager state.

        Args:
            villager_id: Villager ID to load

        Returns:
            VillagerState if found, None otherwise
        """
        if self.storage:
            data = await self.storage.load_villager(villager_id)
            if data:
                return VillagerState.from_dict(data)
        else:
            state = self._cache.get(f"villager:{villager_id}")
            return state

        return None

    async def restore_villager(
        self,
        villager_id: str,
        villager_class: Any,
        llm_provider: Any
    ) -> Optional[Any]:
        """Restore a villager from saved state.

        Args:
            villager_id: Villager ID to restore
            villager_class: Villager class to instantiate
            llm_provider: LLM provider for the villager

        Returns:
            Restored villager instance or None
        """
        state = await self.load_villager_state(villager_id)

        if not state:
            return None

        # Create new villager instance
        villager = villager_class(
            name=state.name,
            llm_provider=llm_provider,
            role=state.role
        )

        # Restore state
        villager.id = state.villager_id
        villager.conversation_history = state.conversation_history
        villager.memory = state.memory
        villager.config = state.config
        villager.created_at = state.created_at

        return villager

    async def save_village_state(
        self,
        village: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Save village state.

        Args:
            village: Village instance to save
            metadata: Optional additional metadata

        Returns:
            True if successful
        """
        # Save each villager
        villager_states = {}
        for villager_id, villager in getattr(village, "villagers", {}).items():
            await self.save_villager_state(villager)

            villager_state = VillagerState(
                villager_id=villager.id,
                name=villager.name,
                role=villager.role,
                conversation_history=getattr(villager, "conversation_history", []),
                memory=getattr(villager, "memory", {}),
                config=getattr(villager, "config", {}),
                created_at=getattr(villager, "created_at", datetime.now()),
                last_updated=datetime.now(),
                metadata={}
            )
            villager_states[villager_id] = villager_state

        # Save village
        state = VillageState(
            village_id=village.id,
            name=village.name,
            villagers=villager_states,
            task_history=getattr(village, "task_history", []),
            config=getattr(village, "config", {}),
            created_at=getattr(village, "created_at", datetime.now()),
            last_updated=datetime.now(),
            metadata=metadata or {}
        )

        if self.storage:
            await self.storage.save_village(village.id, state.to_dict())
        else:
            self._cache[f"village:{village.id}"] = state

        return True

    async def load_village_state(
        self,
        village_id: str
    ) -> Optional[VillageState]:
        """Load village state.

        Args:
            village_id: Village ID to load

        Returns:
            VillageState if found, None otherwise
        """
        if self.storage:
            data = await self.storage.load_village(village_id)
            if data:
                return VillageState.from_dict(data)
        else:
            state = self._cache.get(f"village:{village_id}")
            return state

        return None

    async def restore_village(
        self,
        village_id: str,
        village_class: Any,
        villager_class: Any,
        llm_provider: Any
    ) -> Optional[Any]:
        """Restore a village from saved state.

        Args:
            village_id: Village ID to restore
            village_class: Village class to instantiate
            villager_class: Villager class to instantiate
            llm_provider: LLM provider for villagers

        Returns:
            Restored village instance or None
        """
        state = await self.load_village_state(village_id)

        if not state:
            return None

        # Create new village instance
        village = village_class(name=state.name)
        village.id = state.village_id
        village.task_history = state.task_history
        village.config = state.config
        village.created_at = state.created_at

        # Restore villagers
        for villager_id, villager_state in state.villagers.items():
            villager = await self.restore_villager(
                villager_id,
                villager_class,
                llm_provider
            )
            if villager:
                village.villagers[villager_id] = villager

        return village

    async def create_checkpoint(
        self,
        entity: Any,
        checkpoint_name: str
    ) -> bool:
        """Create a named checkpoint of entity state.

        Args:
            entity: Villager or Village to checkpoint
            checkpoint_name: Name for the checkpoint

        Returns:
            True if successful
        """
        entity_type = entity.__class__.__name__.lower()
        entity_id = entity.id

        if entity_type == "villager":
            state = await self.load_villager_state(entity_id)
            if state:
                self._cache[f"checkpoint:{entity_type}:{entity_id}:{checkpoint_name}"] = state
                return True
        elif entity_type == "village":
            state = await self.load_village_state(entity_id)
            if state:
                self._cache[f"checkpoint:{entity_type}:{entity_id}:{checkpoint_name}"] = state
                return True

        return False

    async def restore_checkpoint(
        self,
        entity_id: str,
        entity_type: str,
        checkpoint_name: str
    ) -> Optional[Any]:
        """Restore from a named checkpoint.

        Args:
            entity_id: Entity ID
            entity_type: Type (villager or village)
            checkpoint_name: Checkpoint name

        Returns:
            Restored state or None
        """
        key = f"checkpoint:{entity_type}:{entity_id}:{checkpoint_name}"
        return self._cache.get(key)

    async def list_checkpoints(
        self,
        entity_id: str,
        entity_type: str
    ) -> list[str]:
        """List available checkpoints for an entity.

        Args:
            entity_id: Entity ID
            entity_type: Type (villager or village)

        Returns:
            List of checkpoint names
        """
        prefix = f"checkpoint:{entity_type}:{entity_id}:"
        checkpoints = []

        for key in self._cache.keys():
            if key.startswith(prefix):
                checkpoint_name = key[len(prefix):]
                checkpoints.append(checkpoint_name)

        return checkpoints

    async def export_state(
        self,
        entity_id: str,
        entity_type: str,
        filepath: str,
        format: str = "json"
    ) -> bool:
        """Export entity state to file.

        Args:
            entity_id: Entity ID
            entity_type: Type (villager or village)
            filepath: Output file path
            format: Export format (json or pickle)

        Returns:
            True if successful
        """
        if entity_type == "villager":
            state = await self.load_villager_state(entity_id)
        elif entity_type == "village":
            state = await self.load_village_state(entity_id)
        else:
            return False

        if not state:
            return False

        if format == "json":
            with open(filepath, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
        elif format == "pickle":
            with open(filepath, "wb") as f:
                pickle.dump(state, f)
        else:
            return False

        return True

    async def import_state(
        self,
        filepath: str,
        format: str = "json"
    ) -> Optional[Any]:
        """Import entity state from file.

        Args:
            filepath: Input file path
            format: Import format (json or pickle)

        Returns:
            Imported state or None
        """
        try:
            if format == "json":
                with open(filepath, "r") as f:
                    data = json.load(f)

                if "villager_id" in data:
                    return VillagerState.from_dict(data)
                elif "village_id" in data:
                    return VillageState.from_dict(data)
            elif format == "pickle":
                with open(filepath, "rb") as f:
                    return pickle.load(f)

        except Exception:
            return None

        return None


# Global state manager instance
_state_manager_instance: Optional[StateManager] = None


def get_state_manager(storage_backend: Optional[Any] = None) -> StateManager:
    """Get global state manager instance.

    Args:
        storage_backend: Optional storage backend

    Returns:
        StateManager instance
    """
    global _state_manager_instance

    if _state_manager_instance is None:
        _state_manager_instance = StateManager(storage_backend)

    return _state_manager_instance
