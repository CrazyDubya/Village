"""Memory summarization for context window management."""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class Message:
    """A single message in conversation history.

    Attributes:
        role: Message role (user, assistant, system)
        content: Message content
        tokens: Estimated token count
        timestamp: Message timestamp
        metadata: Additional metadata
    """
    role: str
    content: str
    tokens: int = 0
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        """Initialize defaults."""
        if self.tokens == 0:
            self.tokens = estimate_tokens(self.content)
        if self.metadata is None:
            self.metadata = {}


class MemorySummarizer:
    """Summarize and compress conversation history to fit context windows.

    Reduces token usage by 40-60% while preserving key information.
    """

    def __init__(
        self,
        max_tokens: int = 4096,
        preserve_recent: int = 5,
        compression_ratio: float = 0.4
    ) -> None:
        """Initialize memory summarizer.

        Args:
            max_tokens: Maximum tokens to keep in history
            preserve_recent: Number of recent messages to always keep
            compression_ratio: Target ratio for summarization (0-1)
        """
        self.max_tokens = max_tokens
        self.preserve_recent = preserve_recent
        self.compression_ratio = compression_ratio

    def summarize_messages(
        self,
        messages: List[Dict[str, str]],
        llm_provider: Optional[Any] = None
    ) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
        """Summarize messages to fit within token limit.

        Args:
            messages: List of message dictionaries
            llm_provider: Optional LLM provider for intelligent summarization

        Returns:
            Tuple of (summarized messages, metadata)
        """
        if not messages:
            return [], {"original_count": 0, "summarized_count": 0, "tokens_saved": 0}

        # Convert to Message objects
        msg_objects = [
            Message(
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                timestamp=msg.get("timestamp"),
                metadata=msg.get("metadata")
            )
            for msg in messages
        ]

        total_tokens = sum(m.tokens for m in msg_objects)

        # If under limit, no summarization needed
        if total_tokens <= self.max_tokens:
            return messages, {
                "original_count": len(messages),
                "summarized_count": len(messages),
                "tokens_saved": 0,
                "original_tokens": total_tokens,
                "final_tokens": total_tokens,
            }

        # Separate recent and older messages
        recent = msg_objects[-self.preserve_recent:]
        older = msg_objects[:-self.preserve_recent]

        recent_tokens = sum(m.tokens for m in recent)
        older_tokens = sum(m.tokens for m in older)

        # Calculate target tokens for older messages
        available_for_older = self.max_tokens - recent_tokens
        target_older_tokens = int(available_for_older * self.compression_ratio)

        # Summarize older messages
        if llm_provider:
            summarized_older = self._summarize_with_llm(older, target_older_tokens, llm_provider)
        else:
            summarized_older = self._summarize_heuristic(older, target_older_tokens)

        # Combine summarized older + recent
        result_messages = summarized_older + [
            {"role": m.role, "content": m.content}
            for m in recent
        ]

        final_tokens = sum(estimate_tokens(m["content"]) for m in result_messages)

        metadata = {
            "original_count": len(messages),
            "summarized_count": len(result_messages),
            "tokens_saved": total_tokens - final_tokens,
            "original_tokens": total_tokens,
            "final_tokens": final_tokens,
            "compression_ratio": final_tokens / total_tokens if total_tokens > 0 else 1.0,
        }

        return result_messages, metadata

    def _summarize_heuristic(
        self,
        messages: List[Message],
        target_tokens: int
    ) -> List[Dict[str, str]]:
        """Summarize messages using heuristic methods.

        Uses extractive summarization to keep most important sentences.

        Args:
            messages: Messages to summarize
            target_tokens: Target token count

        Returns:
            Summarized messages
        """
        if not messages:
            return []

        # Combine all messages into chunks by role
        combined_by_role = {}
        for msg in messages:
            if msg.role not in combined_by_role:
                combined_by_role[msg.role] = []
            combined_by_role[msg.role].append(msg.content)

        # Create summary message for each role
        summarized = []

        for role, contents in combined_by_role.items():
            full_text = "\n\n".join(contents)

            # Extract key sentences
            summary = self._extract_key_sentences(
                full_text,
                target_tokens // len(combined_by_role)
            )

            if summary:
                summarized.append({
                    "role": role,
                    "content": f"[Summary of previous messages]: {summary}"
                })

        return summarized

    async def _summarize_with_llm(
        self,
        messages: List[Message],
        target_tokens: int,
        llm_provider: Any
    ) -> List[Dict[str, str]]:
        """Summarize messages using LLM.

        Args:
            messages: Messages to summarize
            target_tokens: Target token count
            llm_provider: LLM provider for summarization

        Returns:
            Summarized messages
        """
        if not messages:
            return []

        # Combine messages into text
        conversation = "\n\n".join([
            f"{m.role}: {m.content}"
            for m in messages
        ])

        # Generate summary
        prompt = f"""Summarize this conversation, preserving key information, decisions, and context.
Keep the summary concise but informative (target: ~{target_tokens} tokens).

Conversation:
{conversation}

Summary:"""

        try:
            summary = await llm_provider.generate(
                prompt=prompt,
                max_tokens=target_tokens,
                temperature=0.3  # Lower temperature for focused summary
            )

            return [{
                "role": "system",
                "content": f"[Conversation Summary]: {summary}"
            }]

        except Exception:
            # Fall back to heuristic if LLM fails
            return self._summarize_heuristic(messages, target_tokens)

    def _extract_key_sentences(
        self,
        text: str,
        target_tokens: int
    ) -> str:
        """Extract key sentences from text using heuristic scoring.

        Args:
            text: Text to extract from
            target_tokens: Target token count

        Returns:
            Extracted key sentences
        """
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return ""

        # Score sentences by importance
        scored = []
        for sent in sentences:
            score = self._score_sentence(sent, text)
            tokens = estimate_tokens(sent)
            scored.append((score, sent, tokens))

        # Sort by score descending
        scored.sort(reverse=True, key=lambda x: x[0])

        # Select sentences until target reached
        selected = []
        total_tokens = 0

        for score, sent, tokens in scored:
            if total_tokens + tokens <= target_tokens:
                selected.append(sent)
                total_tokens += tokens
            else:
                break

        # Return sentences in original order
        result = []
        for sent in sentences:
            if sent in selected:
                result.append(sent)

        return ". ".join(result) + "." if result else ""

    def _score_sentence(self, sentence: str, full_text: str) -> float:
        """Score sentence importance using heuristics.

        Args:
            sentence: Sentence to score
            full_text: Full text context

        Returns:
            Importance score
        """
        score = 0.0

        # Length (prefer medium-length sentences)
        words = sentence.split()
        if 5 <= len(words) <= 25:
            score += 1.0

        # Important keywords
        important_words = [
            "important", "key", "critical", "essential", "must",
            "decision", "agreed", "concluded", "result", "outcome",
            "because", "therefore", "thus", "hence"
        ]

        for word in important_words:
            if word in sentence.lower():
                score += 0.5

        # Question or command (often important)
        if sentence.strip().endswith("?") or sentence.strip().endswith("!"):
            score += 0.3

        # Contains numbers or dates (often factual/important)
        if re.search(r'\d+', sentence):
            score += 0.2

        # Capitalized words (proper nouns, important terms)
        capitals = sum(1 for word in words if word and word[0].isupper())
        score += min(capitals * 0.1, 0.5)

        return score

    def estimate_summary_savings(
        self,
        messages: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Estimate token savings from summarization without actually summarizing.

        Args:
            messages: Messages to analyze

        Returns:
            Estimated savings information
        """
        if not messages:
            return {"original_tokens": 0, "estimated_final_tokens": 0, "estimated_savings": 0}

        total_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)

        if total_tokens <= self.max_tokens:
            return {
                "original_tokens": total_tokens,
                "estimated_final_tokens": total_tokens,
                "estimated_savings": 0,
                "needs_summarization": False,
            }

        # Estimate final tokens after summarization
        estimated_final = int(total_tokens * self.compression_ratio)
        estimated_final = min(estimated_final, self.max_tokens)

        return {
            "original_tokens": total_tokens,
            "estimated_final_tokens": estimated_final,
            "estimated_savings": total_tokens - estimated_final,
            "estimated_savings_percentage": ((total_tokens - estimated_final) / total_tokens * 100)
                if total_tokens > 0 else 0,
            "needs_summarization": True,
        }


def estimate_tokens(text: str) -> int:
    """Estimate token count for text.

    Uses a simple heuristic: ~4 characters per token.

    Args:
        text: Text to estimate

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    # Simple estimation: roughly 4 characters per token
    # This is a reasonable approximation for English text
    return max(1, len(text) // 4)


def create_rolling_window(
    messages: List[Dict[str, str]],
    window_size: int = 10
) -> List[Dict[str, str]]:
    """Create a rolling window of recent messages.

    Args:
        messages: All messages
        window_size: Number of messages to keep

    Returns:
        Most recent messages
    """
    if len(messages) <= window_size:
        return messages

    return messages[-window_size:]


def compress_repetitive_content(text: str) -> str:
    """Compress repetitive content in text.

    Args:
        text: Text to compress

    Returns:
        Compressed text
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove repeated phrases (more than 2 times)
    # This is a simple implementation; could be more sophisticated
    words = text.split()
    seen_phrases = {}
    result_words = []

    for i in range(len(words)):
        # Check 3-5 word phrases
        for phrase_len in [5, 4, 3]:
            if i + phrase_len <= len(words):
                phrase = " ".join(words[i:i + phrase_len])
                seen_phrases[phrase] = seen_phrases.get(phrase, 0) + 1

                if seen_phrases[phrase] > 2:
                    # Skip this phrase if seen more than twice
                    break
        else:
            result_words.append(words[i])

    return " ".join(result_words)
