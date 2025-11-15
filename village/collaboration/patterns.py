"""Advanced collaboration pattern implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter
import asyncio


class CollaborationPattern(ABC):
    """Abstract base class for collaboration patterns.

    Collaboration patterns define how multiple villagers work together
    to solve problems or make decisions.
    """

    def __init__(self, name: str, description: str) -> None:
        """Initialize collaboration pattern.

        Args:
            name: Pattern name
            description: Pattern description
        """
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(
        self,
        villagers: List[Any],
        task: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute the collaboration pattern.

        Args:
            villagers: List of villagers participating
            task: Task or question to collaborate on
            **kwargs: Additional pattern-specific parameters

        Returns:
            Dictionary containing results and metadata
        """
        pass


class DebatePattern(CollaborationPattern):
    """Adversarial debate pattern where villagers argue different positions.

    This pattern is useful for exploring multiple perspectives and
    stress-testing ideas.
    """

    def __init__(self, rounds: int = 3) -> None:
        """Initialize debate pattern.

        Args:
            rounds: Number of debate rounds
        """
        super().__init__(
            "debate",
            "Adversarial debate with multiple rounds"
        )
        self.rounds = rounds

    async def execute(
        self,
        villagers: List[Any],
        task: str,
        positions: Optional[List[str]] = None,
        judge: Optional[Any] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute a debate between villagers.

        Args:
            villagers: Villagers to participate (typically 2)
            task: Debate topic or question
            positions: Optional specific positions to argue
            judge: Optional judge villager to evaluate
            **kwargs: Additional parameters

        Returns:
            Dictionary with debate history and judgment
        """
        if len(villagers) < 2:
            raise ValueError("Debate requires at least 2 villagers")

        debate_history = []

        # Assign positions if not provided
        if positions is None:
            positions = [
                f"Argue in favor of: {task}",
                f"Argue against: {task}"
            ]
        elif len(positions) != len(villagers):
            raise ValueError("Number of positions must match number of villagers")

        # Opening statements
        for villager, position in zip(villagers, positions):
            response = await villager.process_task(f"{position}\n\nProvide your opening statement.")
            debate_history.append({
                "round": 0,
                "villager": villager.name,
                "position": position,
                "statement": response
            })

        # Debate rounds
        for round_num in range(1, self.rounds + 1):
            for i, villager in enumerate(villagers):
                # Get opponent's last statement
                opponent_idx = (i + 1) % len(villagers)
                opponent_last = debate_history[-len(villagers) + opponent_idx]["statement"]

                prompt = (
                    f"Round {round_num}: Rebut your opponent's argument.\n\n"
                    f"Opponent said: {opponent_last}\n\n"
                    f"Your rebuttal:"
                )

                response = await villager.process_task(prompt)
                debate_history.append({
                    "round": round_num,
                    "villager": villager.name,
                    "statement": response
                })

        # Judge evaluation if provided
        judgment = None
        if judge:
            summary = "\n\n".join([
                f"{entry['villager']} (Round {entry['round']}): {entry['statement']}"
                for entry in debate_history
            ])

            judgment_prompt = (
                f"Evaluate this debate on: {task}\n\n"
                f"Debate transcript:\n{summary}\n\n"
                f"Provide your judgment, explaining which arguments were most compelling and why."
            )

            judgment = await judge.process_task(judgment_prompt)

        return {
            "task": task,
            "pattern": "debate",
            "rounds": self.rounds,
            "participants": [v.name for v in villagers],
            "history": debate_history,
            "judgment": judgment
        }


class VotingPattern(CollaborationPattern):
    """Voting pattern for democratic decision-making.

    Villagers independently evaluate options and vote, with results
    aggregated to reach a decision.
    """

    def __init__(self, voting_method: str = "plurality") -> None:
        """Initialize voting pattern.

        Args:
            voting_method: Method for vote aggregation (plurality, ranked_choice, approval)
        """
        super().__init__(
            "voting",
            f"Democratic voting using {voting_method}"
        )
        self.voting_method = voting_method

    async def execute(
        self,
        villagers: List[Any],
        task: str,
        options: List[str],
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute voting pattern.

        Args:
            villagers: Villagers participating in vote
            task: Decision or question to vote on
            options: List of options to vote on
            **kwargs: Additional parameters

        Returns:
            Dictionary with voting results
        """
        if not options:
            raise ValueError("At least one option required for voting")

        votes = []
        rationales = []

        # Collect votes
        for villager in villagers:
            prompt = (
                f"Vote on: {task}\n\n"
                f"Options:\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)]) + "\n\n"
                f"Respond with your vote (the number) and brief rationale."
            )

            response = await villager.process_task(prompt)

            # Parse vote (simple number extraction)
            vote = None
            for i, opt in enumerate(options):
                if str(i + 1) in response[:10]:  # Check first 10 chars for vote
                    vote = i
                    break

            if vote is not None:
                votes.append(vote)
                rationales.append({
                    "villager": villager.name,
                    "vote": options[vote],
                    "rationale": response
                })

        # Aggregate votes
        if self.voting_method == "plurality":
            vote_counts = Counter(votes)
            winner_idx = vote_counts.most_common(1)[0][0]
            winner = options[winner_idx]
            vote_distribution = {
                options[i]: count for i, count in vote_counts.items()
            }
        else:
            # For now, default to plurality for other methods
            vote_counts = Counter(votes)
            winner_idx = vote_counts.most_common(1)[0][0]
            winner = options[winner_idx]
            vote_distribution = {
                options[i]: count for i, count in vote_counts.items()
            }

        return {
            "task": task,
            "pattern": "voting",
            "method": self.voting_method,
            "options": options,
            "participants": [v.name for v in villagers],
            "votes": rationales,
            "distribution": vote_distribution,
            "winner": winner
        }


class ConsensusPattern(CollaborationPattern):
    """Consensus-building pattern through iterative discussion.

    Villagers discuss and refine positions until reaching agreement
    or identifying key disagreements.
    """

    def __init__(self, max_rounds: int = 3, threshold: float = 0.8) -> None:
        """Initialize consensus pattern.

        Args:
            max_rounds: Maximum discussion rounds
            threshold: Agreement threshold (0-1) to stop early
        """
        super().__init__(
            "consensus",
            "Iterative consensus building"
        )
        self.max_rounds = max_rounds
        self.threshold = threshold

    async def execute(
        self,
        villagers: List[Any],
        task: str,
        moderator: Optional[Any] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute consensus-building pattern.

        Args:
            villagers: Villagers participating
            task: Question or topic to reach consensus on
            moderator: Optional moderator villager to synthesize
            **kwargs: Additional parameters

        Returns:
            Dictionary with consensus results
        """
        discussion_history = []

        # Round 1: Initial positions
        initial_positions = []
        for villager in villagers:
            response = await villager.process_task(
                f"Share your initial position on: {task}"
            )
            initial_positions.append({
                "villager": villager.name,
                "position": response
            })
            discussion_history.append({
                "round": 1,
                "villager": villager.name,
                "statement": response
            })

        # Iterative refinement rounds
        current_round = 2
        consensus_reached = False

        while current_round <= self.max_rounds and not consensus_reached:
            # Moderator or first villager summarizes
            summarizer = moderator if moderator else villagers[0]
            prev_round_statements = [
                s["statement"] for s in discussion_history
                if s["round"] == current_round - 1
            ]

            summary = await summarizer.process_task(
                f"Summarize these positions on {task}:\n\n" +
                "\n\n".join(prev_round_statements)
            )

            # Each villager refines their position
            refined_positions = []
            for villager in villagers:
                prompt = (
                    f"Round {current_round}: Refine your position on: {task}\n\n"
                    f"Summary of previous round: {summary}\n\n"
                    f"Your refined position:"
                )

                response = await villager.process_task(prompt)
                refined_positions.append(response)
                discussion_history.append({
                    "round": current_round,
                    "villager": villager.name,
                    "statement": response
                })

            current_round += 1

        # Final consensus synthesis
        final_positions = [
            s["statement"] for s in discussion_history
            if s["round"] == current_round - 1
        ]

        synthesizer = moderator if moderator else villagers[0]
        consensus = await synthesizer.process_task(
            f"Synthesize a consensus position on: {task}\n\n"
            f"Based on these final positions:\n\n" +
            "\n\n".join(final_positions)
        )

        return {
            "task": task,
            "pattern": "consensus",
            "rounds": current_round - 1,
            "participants": [v.name for v in villagers],
            "history": discussion_history,
            "consensus": consensus,
            "achieved": consensus_reached
        }


class SwarmPattern(CollaborationPattern):
    """Swarm intelligence pattern for parallel exploration and aggregation.

    Multiple villagers independently explore the problem space,
    with results aggregated for a comprehensive solution.
    """

    def __init__(self, aggregation_method: str = "synthesis") -> None:
        """Initialize swarm pattern.

        Args:
            aggregation_method: How to aggregate results (synthesis, voting, best)
        """
        super().__init__(
            "swarm",
            f"Parallel exploration with {aggregation_method} aggregation"
        )
        self.aggregation_method = aggregation_method

    async def execute(
        self,
        villagers: List[Any],
        task: str,
        aggregator: Optional[Any] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute swarm pattern.

        Args:
            villagers: Villagers to participate
            task: Task to solve
            aggregator: Optional villager to aggregate results
            **kwargs: Additional parameters

        Returns:
            Dictionary with swarm results
        """
        # Parallel exploration
        async def explore(villager: Any) -> Tuple[str, str]:
            response = await villager.process_task(task)
            return villager.name, response

        results = await asyncio.gather(*[explore(v) for v in villagers])

        individual_results = [
            {"villager": name, "result": result}
            for name, result in results
        ]

        # Aggregate results
        aggregator_villager = aggregator if aggregator else villagers[0]

        if self.aggregation_method == "synthesis":
            all_results = "\n\n".join([
                f"{r['villager']}: {r['result']}"
                for r in individual_results
            ])

            aggregated = await aggregator_villager.process_task(
                f"Synthesize these different approaches to: {task}\n\n{all_results}"
            )

        elif self.aggregation_method == "best":
            all_results = "\n\n".join([
                f"Option {i+1} from {r['villager']}: {r['result']}"
                for i, r in enumerate(individual_results)
            ])

            aggregated = await aggregator_villager.process_task(
                f"Select and explain the best approach to: {task}\n\n{all_results}"
            )

        else:  # Default to synthesis
            all_results = "\n\n".join([
                f"{r['villager']}: {r['result']}"
                for r in individual_results
            ])

            aggregated = await aggregator_villager.process_task(
                f"Aggregate these results for: {task}\n\n{all_results}"
            )

        return {
            "task": task,
            "pattern": "swarm",
            "aggregation": self.aggregation_method,
            "participants": [v.name for v in villagers],
            "individual_results": individual_results,
            "aggregated_result": aggregated
        }


class HierarchicalPattern(CollaborationPattern):
    """Hierarchical collaboration with delegation and synthesis.

    Work is delegated to specialized villagers and synthesized
    up through a hierarchy.
    """

    def __init__(self) -> None:
        """Initialize hierarchical pattern."""
        super().__init__(
            "hierarchical",
            "Hierarchical delegation and synthesis"
        )

    async def execute(
        self,
        villagers: List[Any],
        task: str,
        leader: Any,
        delegation_map: Optional[Dict[str, List[str]]] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Execute hierarchical pattern.

        Args:
            villagers: Villagers to participate
            task: Task to solve
            leader: Leader villager who delegates and synthesizes
            delegation_map: Mapping of subtasks to villager roles
            **kwargs: Additional parameters

        Returns:
            Dictionary with hierarchical results
        """
        # Leader breaks down the task
        breakdown_prompt = (
            f"Break down this task into subtasks that can be delegated: {task}\n\n"
            f"Available roles: {', '.join([v.role for v in villagers])}\n\n"
            f"List the subtasks."
        )

        breakdown = await leader.process_task(breakdown_prompt)

        # If delegation map not provided, distribute evenly
        if delegation_map is None:
            # Simple round-robin delegation
            subtasks = breakdown.split("\n")
            delegation_map = {
                subtask: [villagers[i % len(villagers)].role]
                for i, subtask in enumerate(subtasks) if subtask.strip()
            }

        # Execute subtasks
        subtask_results = []

        for subtask, assigned_roles in delegation_map.items():
            # Find villagers with assigned roles
            assigned_villagers = [
                v for v in villagers
                if v.role in assigned_roles
            ]

            if assigned_villagers:
                villager = assigned_villagers[0]
                result = await villager.process_task(subtask)
                subtask_results.append({
                    "subtask": subtask,
                    "assigned_to": villager.name,
                    "role": villager.role,
                    "result": result
                })

        # Leader synthesizes results
        synthesis_prompt = (
            f"Synthesize these subtask results into a complete solution for: {task}\n\n" +
            "\n\n".join([
                f"Subtask: {r['subtask']}\nCompleted by {r['assigned_to']} ({r['role']}): {r['result']}"
                for r in subtask_results
            ])
        )

        final_result = await leader.process_task(synthesis_prompt)

        return {
            "task": task,
            "pattern": "hierarchical",
            "leader": leader.name,
            "breakdown": breakdown,
            "delegation": delegation_map,
            "subtask_results": subtask_results,
            "final_result": final_result
        }
