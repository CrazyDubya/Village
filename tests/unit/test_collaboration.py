"""Unit tests for collaboration patterns."""

import pytest
from unittest.mock import Mock, AsyncMock
from village.collaboration.patterns import (
    DebatePattern,
    VotingPattern,
    ConsensusPattern,
    SwarmPattern,
    HierarchicalPattern,
)


@pytest.fixture
def mock_villager():
    """Create a mock villager."""
    villager = Mock()
    villager.name = "test_villager"
    villager.role = "analyst"
    villager.process_task = AsyncMock(return_value="Mock result")
    return villager


@pytest.fixture
def mock_villagers():
    """Create multiple mock villagers."""
    villagers = []
    for i in range(3):
        villager = Mock()
        villager.name = f"villager_{i}"
        villager.role = f"role_{i}"
        villager.process_task = AsyncMock(return_value=f"Result from villager {i}")
        villagers.append(villager)
    return villagers


@pytest.mark.asyncio
async def test_debate_pattern_initialization():
    """Test debate pattern initialization."""
    pattern = DebatePattern(rounds=3)

    assert pattern.name == "debate"
    assert pattern.rounds == 3


@pytest.mark.asyncio
async def test_debate_pattern_execution(mock_villagers):
    """Test debate pattern execution."""
    pattern = DebatePattern(rounds=2)
    judge = Mock()
    judge.name = "judge"
    judge.process_task = AsyncMock(return_value="Judgment result")

    result = await pattern.execute(
        villagers=mock_villagers[:2],
        task="AI is beneficial",
        judge=judge
    )

    assert result["pattern"] == "debate"
    assert result["rounds"] == 2
    assert len(result["participants"]) == 2
    assert "history" in result
    assert result["judgment"] == "Judgment result"


@pytest.mark.asyncio
async def test_debate_pattern_requires_two_villagers(mock_villager):
    """Test that debate requires at least 2 villagers."""
    pattern = DebatePattern(rounds=2)

    with pytest.raises(ValueError, match="at least 2 villagers"):
        await pattern.execute(
            villagers=[mock_villager],
            task="Test topic"
        )


@pytest.mark.asyncio
async def test_voting_pattern_initialization():
    """Test voting pattern initialization."""
    pattern = VotingPattern(voting_method="plurality")

    assert pattern.name == "voting"
    assert pattern.voting_method == "plurality"


@pytest.mark.asyncio
async def test_voting_pattern_execution(mock_villagers):
    """Test voting pattern execution."""
    # Mock villagers to return votes
    for i, villager in enumerate(mock_villagers):
        villager.process_task = AsyncMock(return_value=f"{i % 2 + 1}. My vote because...")

    pattern = VotingPattern(voting_method="plurality")
    options = ["Option A", "Option B"]

    result = await pattern.execute(
        villagers=mock_villagers,
        task="Choose the best option",
        options=options
    )

    assert result["pattern"] == "voting"
    assert result["method"] == "plurality"
    assert len(result["votes"]) == 3
    assert "winner" in result
    assert "distribution" in result


@pytest.mark.asyncio
async def test_voting_pattern_requires_options(mock_villagers):
    """Test that voting requires options."""
    pattern = VotingPattern()

    with pytest.raises(ValueError, match="At least one option"):
        await pattern.execute(
            villagers=mock_villagers,
            task="Test",
            options=[]
        )


@pytest.mark.asyncio
async def test_consensus_pattern_initialization():
    """Test consensus pattern initialization."""
    pattern = ConsensusPattern(max_rounds=3, threshold=0.8)

    assert pattern.name == "consensus"
    assert pattern.max_rounds == 3
    assert pattern.threshold == 0.8


@pytest.mark.asyncio
async def test_consensus_pattern_execution(mock_villagers):
    """Test consensus pattern execution."""
    moderator = Mock()
    moderator.name = "moderator"
    moderator.process_task = AsyncMock(return_value="Consensus achieved")

    pattern = ConsensusPattern(max_rounds=2)

    result = await pattern.execute(
        villagers=mock_villagers,
        task="What is the best approach?",
        moderator=moderator
    )

    assert result["pattern"] == "consensus"
    assert len(result["participants"]) == 3
    assert "history" in result
    assert "consensus" in result


@pytest.mark.asyncio
async def test_swarm_pattern_initialization():
    """Test swarm pattern initialization."""
    pattern = SwarmPattern(aggregation_method="synthesis")

    assert pattern.name == "swarm"
    assert pattern.aggregation_method == "synthesis"


@pytest.mark.asyncio
async def test_swarm_pattern_execution(mock_villagers):
    """Test swarm pattern execution."""
    pattern = SwarmPattern(aggregation_method="synthesis")

    result = await pattern.execute(
        villagers=mock_villagers,
        task="Solve this problem"
    )

    assert result["pattern"] == "swarm"
    assert result["aggregation"] == "synthesis"
    assert len(result["individual_results"]) == 3
    assert "aggregated_result" in result


@pytest.mark.asyncio
async def test_hierarchical_pattern_initialization():
    """Test hierarchical pattern initialization."""
    pattern = HierarchicalPattern()

    assert pattern.name == "hierarchical"


@pytest.mark.asyncio
async def test_hierarchical_pattern_execution(mock_villagers):
    """Test hierarchical pattern execution."""
    leader = Mock()
    leader.name = "leader"
    leader.role = "manager"
    leader.process_task = AsyncMock(side_effect=[
        "Subtask 1\nSubtask 2\nSubtask 3",  # Breakdown
        "Final synthesis"  # Final result
    ])

    pattern = HierarchicalPattern()

    result = await pattern.execute(
        villagers=mock_villagers,
        task="Complete this project",
        leader=leader
    )

    assert result["pattern"] == "hierarchical"
    assert result["leader"] == "leader"
    assert "breakdown" in result
    assert "final_result" in result
