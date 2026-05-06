"""Analyst agent implementation."""

from __future__ import annotations

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient


logger = logging.getLogger(__name__)


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate `state.analysis_notes`."""

        query = state.request.query.strip()
        source_block = self._format_sources(state)
        user_prompt = (
            f"Query: {query}\n"
            f"Audience: {state.request.audience}\n\n"
            f"Research notes:\n{state.research_notes or 'No research notes yet.'}\n\n"
            f"Sources:\n{source_block or '- No sources available.'}\n"
        )
        response = self.llm_client.complete(
            "You are the analyst agent. Extract claims, compare viewpoints, and flag weak evidence.",
            user_prompt,
        )
        state.analysis_notes = response.content.strip() or self._fallback_analysis(state)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=state.analysis_notes,
                metadata={
                    "has_research_notes": bool(state.research_notes),
                    "source_count": len(state.sources),
                },
            )
        )
        state.add_trace_event(
            "analyst.run",
            {"query": query, "has_research_notes": bool(state.research_notes)},
        )
        logger.info("Analyst produced analysis notes")
        return state

    def _format_sources(self, state: ResearchState) -> str:
        lines = []
        for index, source in enumerate(state.sources, start=1):
            lines.append(f"- [{index}] {source.title} | {source.url or 'n/a'} | {source.snippet}")
        return "\n".join(lines)

    def _fallback_analysis(self, state: ResearchState) -> str:
        lines = [f"Analysis for {state.request.query}", "", "Key claims:"]
        if state.research_notes:
            lines.append(f"- {state.research_notes.splitlines()[0]}")
        else:
            lines.append("- The research stage did not produce notes, so the analysis is conservative.")
        lines.extend(
            [
                "",
                "Comparison:",
                "- Stronger claims are the ones repeated across multiple sources.",
                "- Weaker claims should be treated as hypotheses unless the sources are explicit.",
                "",
                "Evidence gaps:",
            ]
        )
        if state.sources:
            for index, source in enumerate(state.sources[:3], start=1):
                lines.append(f"- [{index}] {source.title}")
        else:
            lines.append("- No sources were available for verification.")
        return "\n".join(lines)
