"""Unit tests for workflow templates."""

import pytest
from unittest.mock import Mock, AsyncMock
from village.workflows.templates import (
    WorkflowStep,
    SequentialWorkflow,
    ParallelWorkflow,
    DebateWorkflow,
    ConsensusWorkflow,
    ResearchWorkflow,
    CodeReviewWorkflow,
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
def mock_village(mock_villager):
    """Create a mock village."""
    village = Mock()
    village.get_villager_by_role = Mock(return_value=mock_villager)
    return village


def test_workflow_step_creation():
    """Test WorkflowStep creation."""
    step = WorkflowStep(
        name="test_step",
        villager_role="analyst",
        prompt_template="Test prompt: {task}"
    )

    assert step.name == "test_step"
    assert step.villager_role == "analyst"
    assert step.prompt_template == "Test prompt: {task}"
    assert step.depends_on == []


def test_sequential_workflow_definition():
    """Test sequential workflow definition."""
    steps = [
        {"name": "step1", "role": "analyst", "prompt": "Do task 1"},
        {"name": "step2", "role": "reviewer", "prompt": "Do task 2"},
        {"name": "step3", "role": "synthesizer", "prompt": "Do task 3"},
    ]

    workflow = SequentialWorkflow(steps)
    workflow_steps = workflow.get_steps()

    assert len(workflow_steps) == 3
    assert workflow_steps[0].depends_on == []
    assert workflow_steps[1].depends_on == ["step1"]
    assert workflow_steps[2].depends_on == ["step2"]


@pytest.mark.asyncio
async def test_sequential_workflow_execution(mock_village):
    """Test sequential workflow execution."""
    steps = [
        {"name": "step1", "role": "analyst", "prompt": "Task: {task}"},
        {"name": "step2", "role": "analyst", "prompt": "Task: {task}"},
    ]

    workflow = SequentialWorkflow(steps)
    results = await workflow.execute(mock_village, {"task": "test"})

    assert len(results) == 2
    assert "step1" in results
    assert "step2" in results


def test_parallel_workflow_definition():
    """Test parallel workflow definition."""
    steps = [
        {"name": "step1", "role": "analyst", "prompt": "Do task 1"},
        {"name": "step2", "role": "reviewer", "prompt": "Do task 2"},
    ]

    workflow = ParallelWorkflow(steps)
    workflow_steps = workflow.get_steps()

    assert len(workflow_steps) == 2
    # Parallel steps should have no dependencies
    assert all(step.depends_on == [] for step in workflow_steps)


def test_debate_workflow_definition():
    """Test debate workflow definition."""
    workflow = DebateWorkflow(
        topic="AI is beneficial",
        rounds=2,
        proposition_role="proponent",
        opposition_role="opponent"
    )

    steps = workflow.get_steps()

    # Should have opening statements + 2 rounds + judgment
    # Opening: 2, Rounds: 2*2=4, Judgment: 1 = 7 total
    assert len(steps) >= 5


def test_consensus_workflow_definition():
    """Test consensus workflow definition."""
    workflow = ConsensusWorkflow(
        question="What is the best approach?",
        participant_roles=["analyst", "researcher"],
        rounds=2
    )

    steps = workflow.get_steps()

    # Should have initial positions + discussion rounds + final consensus
    assert len(steps) > 3


def test_research_workflow_definition():
    """Test research workflow definition."""
    workflow = ResearchWorkflow(topic="Machine Learning")
    steps = workflow.get_steps()

    # Should have all research phases
    step_names = [s.name for s in steps]
    assert "literature_review" in step_names
    assert "data_analysis" in step_names
    assert "methodology" in step_names
    assert "synthesis" in step_names
    assert "peer_review" in step_names
    assert "final_report" in step_names


def test_code_review_workflow_definition():
    """Test code review workflow definition."""
    code = "def hello(): return 'world'"
    workflow = CodeReviewWorkflow(code=code, language="python")
    steps = workflow.get_steps()

    # Should have all review types + consolidation
    step_names = [s.name for s in steps]
    assert "security_review" in step_names
    assert "performance_review" in step_names
    assert "style_review" in step_names
    assert "test_review" in step_names
    assert "consolidation" in step_names


def test_workflow_prompt_formatting():
    """Test prompt formatting with context."""
    step = WorkflowStep(
        name="test",
        villager_role="analyst",
        prompt_template="Task: {task}, Result: {prev_result}"
    )

    workflow = SequentialWorkflow([{"name": "test", "role": "analyst", "prompt": "test"}])
    formatted = workflow.format_prompt(step, {"task": "analyze", "prev_result": "done"})

    assert "analyze" in formatted
    assert "done" in formatted
