"""Optional critic agent implementation."""

from __future__ import annotations

import logging
import re

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    """Optional fact-checking and safety-review agent."""

    name = "critic"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer and append findings."""

        query = state.request.query.strip()
        final_answer = state.final_answer or ""
        source_count = len(state.sources)
        cited_sources = {int(match) for match in re.findall(r"\[(\d+)\]", final_answer)}
        issues: list[str] = []
        if not final_answer.strip():
            issues.append("Final answer is missing.")
        if source_count and not cited_sources:
            issues.append("Final answer does not contain explicit citations.")
        if cited_sources and max(cited_sources) > source_count:
            issues.append("Final answer references a source index that is not in the research set.")

        user_prompt = (
            f"Query: {query}\n\n"
            f"Final answer:\n{final_answer or 'No final answer available.'}\n\n"
            f"Source count: {source_count}\n"
            f"Cited source indices: {sorted(cited_sources) or 'none'}\n\n"
            "Assess citation coverage, unsupported claims, and whether the answer matches the evidence."
        )
        response = self.llm_client.complete(
            "You are the critic agent. Find hallucinations, missing citations, or unresolved evidence gaps.",
            user_prompt,
        )
        review = response.content.strip() or self._fallback_review(query, issues)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=review,
                metadata={"issue_count": len(issues), "cited_sources": sorted(cited_sources)},
            )
        )
        if issues:
            state.errors.extend(issues)
        state.add_trace_event(
            "critic.run",
            {"query": query, "issues": issues, "cited_sources": sorted(cited_sources)},
        )
        logger.info("Critic found %s issue(s)", len(issues))
        return state

    def _fallback_review(self, query: str, issues: list[str]) -> str:
        if not issues:
            return f"Critic review for {query}: the answer appears internally consistent and sufficiently cited."
        joined_issues = "; ".join(issues)
        return f"Critic review for {query}: {joined_issues}"
