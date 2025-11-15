"""Workflow template implementations for common collaboration patterns."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass
import asyncio


@dataclass
class WorkflowStep:
    """A single step in a workflow.

    Attributes:
        name: Step name
        villager_role: Role of villager to execute this step
        prompt_template: Template for the prompt
        depends_on: List of step names this depends on
        max_tokens: Maximum tokens for generation
        temperature: Sampling temperature
    """
    name: str
    villager_role: str
    prompt_template: str
    depends_on: List[str] = None
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize defaults."""
        if self.depends_on is None:
            self.depends_on = []
        if self.metadata is None:
            self.metadata = {}


class WorkflowTemplate(ABC):
    """Abstract base class for workflow templates.

    Workflow templates define common patterns for villager collaboration.
    """

    def __init__(self, name: str, description: str) -> None:
        """Initialize workflow template.

        Args:
            name: Workflow name
            description: Workflow description
        """
        self.name = name
        self.description = description
        self.steps: List[WorkflowStep] = []
        self.results: Dict[str, Any] = {}

    @abstractmethod
    def define_steps(self) -> List[WorkflowStep]:
        """Define the workflow steps.

        Returns:
            List of workflow steps
        """
        pass

    def get_steps(self) -> List[WorkflowStep]:
        """Get workflow steps.

        Returns:
            List of workflow steps
        """
        if not self.steps:
            self.steps = self.define_steps()
        return self.steps

    def format_prompt(self, step: WorkflowStep, context: Dict[str, Any]) -> str:
        """Format a step's prompt with context.

        Args:
            step: Workflow step
            context: Context variables for template

        Returns:
            Formatted prompt
        """
        return step.prompt_template.format(**context)

    async def execute(
        self,
        village: Any,
        context: Dict[str, Any],
        on_step_complete: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Execute the workflow.

        Args:
            village: Village instance to execute on
            context: Initial context variables
            on_step_complete: Optional callback after each step

        Returns:
            Dictionary of results from all steps
        """
        self.results = {}
        steps = self.get_steps()

        for step in steps:
            # Wait for dependencies
            for dep in step.depends_on:
                if dep not in self.results:
                    raise ValueError(f"Step {step.name} depends on {dep} which hasn't completed")

            # Add step dependencies to context
            step_context = context.copy()
            for dep in step.depends_on:
                step_context[f"{dep}_result"] = self.results[dep]

            # Format prompt
            prompt = self.format_prompt(step, step_context)

            # Find villager with the required role
            villager = village.get_villager_by_role(step.villager_role)
            if not villager:
                raise ValueError(f"No villager found with role {step.villager_role}")

            # Execute step
            result = await villager.process_task(
                prompt,
                max_tokens=step.max_tokens,
                temperature=step.temperature
            )

            # Store result
            self.results[step.name] = result

            # Call completion callback
            if on_step_complete:
                await on_step_complete(step, result)

        return self.results


class SequentialWorkflow(WorkflowTemplate):
    """Sequential workflow where steps execute one after another."""

    def __init__(self, steps: List[Dict[str, Any]]) -> None:
        """Initialize sequential workflow.

        Args:
            steps: List of step definitions
        """
        super().__init__("sequential", "Execute steps in sequence")
        self.step_definitions = steps

    def define_steps(self) -> List[WorkflowStep]:
        """Define sequential steps."""
        steps = []
        prev_step = None

        for step_def in self.step_definitions:
            step = WorkflowStep(
                name=step_def["name"],
                villager_role=step_def["role"],
                prompt_template=step_def["prompt"],
                depends_on=[prev_step] if prev_step else [],
                max_tokens=step_def.get("max_tokens"),
                temperature=step_def.get("temperature", 0.7),
                metadata=step_def.get("metadata", {})
            )
            steps.append(step)
            prev_step = step.name

        return steps


class ParallelWorkflow(WorkflowTemplate):
    """Parallel workflow where independent steps execute concurrently."""

    def __init__(self, steps: List[Dict[str, Any]]) -> None:
        """Initialize parallel workflow.

        Args:
            steps: List of step definitions
        """
        super().__init__("parallel", "Execute steps in parallel")
        self.step_definitions = steps

    def define_steps(self) -> List[WorkflowStep]:
        """Define parallel steps."""
        return [
            WorkflowStep(
                name=step_def["name"],
                villager_role=step_def["role"],
                prompt_template=step_def["prompt"],
                depends_on=[],  # No dependencies for parallel execution
                max_tokens=step_def.get("max_tokens"),
                temperature=step_def.get("temperature", 0.7),
                metadata=step_def.get("metadata", {})
            )
            for step_def in self.step_definitions
        ]

    async def execute(
        self,
        village: Any,
        context: Dict[str, Any],
        on_step_complete: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Execute steps in parallel.

        Args:
            village: Village instance
            context: Context variables
            on_step_complete: Optional callback

        Returns:
            Dictionary of results
        """
        self.results = {}
        steps = self.get_steps()

        async def execute_step(step: WorkflowStep) -> None:
            prompt = self.format_prompt(step, context)
            villager = village.get_villager_by_role(step.villager_role)
            if not villager:
                raise ValueError(f"No villager found with role {step.villager_role}")

            result = await villager.process_task(
                prompt,
                max_tokens=step.max_tokens,
                temperature=step.temperature
            )

            self.results[step.name] = result

            if on_step_complete:
                await on_step_complete(step, result)

        # Execute all steps concurrently
        await asyncio.gather(*[execute_step(step) for step in steps])

        return self.results


class DebateWorkflow(WorkflowTemplate):
    """Debate workflow for adversarial collaboration."""

    def __init__(
        self,
        topic: str,
        rounds: int = 3,
        proposition_role: str = "proponent",
        opposition_role: str = "opponent",
        judge_role: str = "judge"
    ) -> None:
        """Initialize debate workflow.

        Args:
            topic: Debate topic
            rounds: Number of debate rounds
            proposition_role: Role for proposition side
            opposition_role: Role for opposition side
            judge_role: Role for judge
        """
        super().__init__("debate", "Adversarial debate workflow")
        self.topic = topic
        self.rounds = rounds
        self.proposition_role = proposition_role
        self.opposition_role = opposition_role
        self.judge_role = judge_role

    def define_steps(self) -> List[WorkflowStep]:
        """Define debate steps."""
        steps = []

        # Opening statements
        steps.append(WorkflowStep(
            name="proposition_opening",
            villager_role=self.proposition_role,
            prompt_template=f"Present your opening argument in favor of: {self.topic}",
            depends_on=[]
        ))

        steps.append(WorkflowStep(
            name="opposition_opening",
            villager_role=self.opposition_role,
            prompt_template=f"Present your opening argument against: {self.topic}",
            depends_on=[]
        ))

        # Debate rounds
        prev_prop = "proposition_opening"
        prev_opp = "opposition_opening"

        for round_num in range(1, self.rounds + 1):
            # Proposition rebuttal
            prop_step = f"proposition_round_{round_num}"
            steps.append(WorkflowStep(
                name=prop_step,
                villager_role=self.proposition_role,
                prompt_template=f"Round {round_num}: Rebut the opposition's arguments. "
                               f"Opposition said: {{{prev_opp}_result}}",
                depends_on=[prev_opp]
            ))

            # Opposition rebuttal
            opp_step = f"opposition_round_{round_num}"
            steps.append(WorkflowStep(
                name=opp_step,
                villager_role=self.opposition_role,
                prompt_template=f"Round {round_num}: Rebut the proposition's arguments. "
                               f"Proposition said: {{{prop_step}_result}}",
                depends_on=[prop_step]
            ))

            prev_prop = prop_step
            prev_opp = opp_step

        # Final judgment
        steps.append(WorkflowStep(
            name="judgment",
            villager_role=self.judge_role,
            prompt_template=f"Evaluate both sides of the debate on: {self.topic}. "
                           f"Proposition's final argument: {{{prev_prop}_result}}. "
                           f"Opposition's final argument: {{{prev_opp}_result}}. "
                           f"Provide your judgment and reasoning.",
            depends_on=[prev_prop, prev_opp]
        ))

        return steps


class ConsensusWorkflow(WorkflowTemplate):
    """Consensus-building workflow using voting and discussion."""

    def __init__(
        self,
        question: str,
        participant_roles: List[str],
        rounds: int = 2,
        moderator_role: str = "moderator"
    ) -> None:
        """Initialize consensus workflow.

        Args:
            question: Question to reach consensus on
            participant_roles: Roles of participating villagers
            rounds: Number of discussion rounds
            moderator_role: Role of moderator
        """
        super().__init__("consensus", "Consensus-building workflow")
        self.question = question
        self.participant_roles = participant_roles
        self.rounds = rounds
        self.moderator_role = moderator_role

    def define_steps(self) -> List[WorkflowStep]:
        """Define consensus-building steps."""
        steps = []

        # Initial positions
        initial_steps = []
        for i, role in enumerate(self.participant_roles):
            step_name = f"initial_position_{role}"
            steps.append(WorkflowStep(
                name=step_name,
                villager_role=role,
                prompt_template=f"Share your initial position on: {self.question}",
                depends_on=[]
            ))
            initial_steps.append(step_name)

        # Discussion rounds
        prev_round_steps = initial_steps
        for round_num in range(1, self.rounds + 1):
            round_steps = []

            # Moderator summarizes previous round
            summary_step = f"summary_round_{round_num}"
            steps.append(WorkflowStep(
                name=summary_step,
                villager_role=self.moderator_role,
                prompt_template=f"Summarize the positions from the previous round: "
                               + " ".join([f"{{{step}_result}}" for step in prev_round_steps]),
                depends_on=prev_round_steps
            ))

            # Each participant responds
            for role in self.participant_roles:
                step_name = f"round_{round_num}_{role}"
                steps.append(WorkflowStep(
                    name=step_name,
                    villager_role=role,
                    prompt_template=f"Round {round_num}: Based on the summary ({{{summary_step}_result}}), "
                                   f"refine your position on: {self.question}",
                    depends_on=[summary_step]
                ))
                round_steps.append(step_name)

            prev_round_steps = round_steps

        # Final consensus
        steps.append(WorkflowStep(
            name="final_consensus",
            villager_role=self.moderator_role,
            prompt_template=f"Synthesize a consensus position based on final round: "
                           + " ".join([f"{{{step}_result}}" for step in prev_round_steps]),
            depends_on=prev_round_steps
        ))

        return steps


class ResearchWorkflow(WorkflowTemplate):
    """Research workflow for comprehensive analysis."""

    def __init__(self, topic: str) -> None:
        """Initialize research workflow.

        Args:
            topic: Research topic
        """
        super().__init__("research", "Comprehensive research workflow")
        self.topic = topic

    def define_steps(self) -> List[WorkflowStep]:
        """Define research workflow steps."""
        return [
            WorkflowStep(
                name="literature_review",
                villager_role="researcher",
                prompt_template=f"Conduct a literature review on: {self.topic}",
                depends_on=[]
            ),
            WorkflowStep(
                name="data_analysis",
                villager_role="analyst",
                prompt_template=f"Analyze data related to: {self.topic}",
                depends_on=[]
            ),
            WorkflowStep(
                name="methodology",
                villager_role="methodologist",
                prompt_template=f"Design research methodology for: {self.topic}. "
                               f"Literature: {{literature_review_result}}",
                depends_on=["literature_review"]
            ),
            WorkflowStep(
                name="synthesis",
                villager_role="synthesizer",
                prompt_template=f"Synthesize findings on: {self.topic}. "
                               f"Literature: {{literature_review_result}}. "
                               f"Analysis: {{data_analysis_result}}. "
                               f"Methodology: {{methodology_result}}",
                depends_on=["literature_review", "data_analysis", "methodology"]
            ),
            WorkflowStep(
                name="peer_review",
                villager_role="reviewer",
                prompt_template=f"Peer review the research synthesis: {{synthesis_result}}",
                depends_on=["synthesis"]
            ),
            WorkflowStep(
                name="final_report",
                villager_role="writer",
                prompt_template=f"Write final research report on: {self.topic}. "
                               f"Synthesis: {{synthesis_result}}. "
                               f"Review: {{peer_review_result}}",
                depends_on=["synthesis", "peer_review"]
            )
        ]


class CodeReviewWorkflow(WorkflowTemplate):
    """Code review workflow for software development."""

    def __init__(self, code: str, language: str = "python") -> None:
        """Initialize code review workflow.

        Args:
            code: Code to review
            language: Programming language
        """
        super().__init__("code_review", "Code review workflow")
        self.code = code
        self.language = language

    def define_steps(self) -> List[WorkflowStep]:
        """Define code review steps."""
        return [
            WorkflowStep(
                name="security_review",
                villager_role="security_expert",
                prompt_template=f"Review this {self.language} code for security vulnerabilities:\n\n{self.code}",
                depends_on=[]
            ),
            WorkflowStep(
                name="performance_review",
                villager_role="performance_expert",
                prompt_template=f"Review this {self.language} code for performance issues:\n\n{self.code}",
                depends_on=[]
            ),
            WorkflowStep(
                name="style_review",
                villager_role="style_expert",
                prompt_template=f"Review this {self.language} code for style and best practices:\n\n{self.code}",
                depends_on=[]
            ),
            WorkflowStep(
                name="test_review",
                villager_role="test_expert",
                prompt_template=f"Review test coverage for this {self.language} code:\n\n{self.code}",
                depends_on=[]
            ),
            WorkflowStep(
                name="consolidation",
                villager_role="lead_reviewer",
                prompt_template=f"Consolidate code review feedback. "
                               f"Security: {{security_review_result}}. "
                               f"Performance: {{performance_review_result}}. "
                               f"Style: {{style_review_result}}. "
                               f"Testing: {{test_review_result}}",
                depends_on=["security_review", "performance_review", "style_review", "test_review"]
            )
        ]
